"""Captions: reading them from subtitle files, and drawing them with otto.

The one module that knows both what a caption is on the way in and what it
becomes on the way out (contract K2):

- **Parsing.** `parse(format, text)` reads SubRip (`srt`), WebVTT (`vtt`) and
  JSON. Subtitle files arrive from every tool there is, so the readers are
  forgiving where forgiveness is unambiguous -- a byte-order mark, CRLF or CR
  line ends, `,` or `.` before the milliseconds, hours past 99 or no hours at
  all, cue identifiers or none, WebVTT cue settings and NOTE/STYLE/REGION
  blocks, markup inside a cue -- and say which line they could not read when
  it is not.
- **Lists.** `checked_captions` holds a list to what a project or a render
  stores: in order, and not too many.
- **Drawing.** `caption_clips` turns captions into one textBox template clip
  each, appended after the timeline's clips so they are drawn on top, with
  explicit timing and no fades. The style's fields are the template's own;
  what a style leaves out is decided here, relative to the frame being
  rendered: the size, the margin, how wide the box is.
- **Transcripts.** `captions_from_transcript` turns what an audio engine heard
  into captions a person can read in the time they are shown for, using the
  engine's word timings to break long stretches of speech.
"""

import html
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError

from ..models.captions import (
    MAX_CAPTION_CHARS,
    Caption,
    CaptionStyle,
    clean_caption_text,
)

# --- lists ------------------------------------------------------------------

# The most captions one project or render may carry. Each is a template clip
# the renderer builds before it draws a frame, so this bounds a render's
# memory as much as anything: a thousand is well over an hour of speech.
MAX_CAPTIONS = 1000


class TooManyCaptions(ValueError):
    pass


def checked_captions(captions: Optional[Iterable[Caption]]) -> List[Caption]:
    """`captions` in order of when they start (then end); TooManyCaptions
    when there are more than MAX_CAPTIONS."""
    ordered = sorted(captions or [], key=lambda c: (c.start, c.end))
    if len(ordered) > MAX_CAPTIONS:
        raise TooManyCaptions(
            f'{len(ordered)} captions is more than the {MAX_CAPTIONS} a project '
            'may carry'
        )
    return ordered


# --- parsing ----------------------------------------------------------------

FORMATS = ('srt', 'vtt', 'json')


class CaptionFormatError(ValueError):
    """A subtitle file that cannot be read. The message names the line."""


@dataclass
class Parsed:
    captions: List[Caption]
    # Cues left out because they had no text, or no length.
    skipped: int = 0


# hh:mm:ss,ttt -- or mm:ss.ttt, or more hours than two digits hold.
_TIME = r'(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,9}))?'
_TIMING = re.compile(rf'^\s*{_TIME}\s*-->\s*{_TIME}(?:\s+.*)?\s*$')
_TIMESTAMP = re.compile(rf'^\s*{_TIME}\s*$')
_INDEX = re.compile(r'^\s*\d+\s*$')
# Markup a cue can hold, none of which a template draws: SubRip's <i>, <b>,
# <font color=...>; WebVTT's <c.yellow>, <v Speaker>, <00:00:01.000>, <ruby>;
# and ASS override codes, {\an8}, which some SubRip files carry.
_TAG = re.compile(r'<[^<>\n]*>')
_ASS = re.compile(r'\{\\[^{}\n]*\}')
# A WebVTT block that is not a cue.
_VTT_BLOCK = re.compile(r'^(NOTE|STYLE|REGION)(\s|$)')


def _seconds(groups, where) -> float:
    hours, minutes, seconds, fraction = groups
    if int(seconds) >= 60 or (hours is not None and int(minutes) >= 60):
        raise CaptionFormatError(
            f'{where}: {":".join(g for g in groups[:3] if g)} ' 'is not a time'
        )
    total = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    if fraction:
        total += int(fraction) / 10 ** len(fraction)
    return total


def _timing(line, where):
    match = _TIMING.match(line)
    if not match:
        return None
    groups = match.groups()
    return _seconds(groups[:4], where), _seconds(groups[4:8], where)


def _cue_text(lines) -> str:
    text = '\n'.join(lines)
    text = _ASS.sub('', text)
    text = _TAG.sub('', text)
    return clean_caption_text(html.unescape(text))


def _normalised(text) -> List[str]:
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    text = str(text).lstrip('﻿')
    return text.replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _cues(text, vtt=False):
    """(start, end, text, line number) for every cue in a SubRip or WebVTT
    file. The two share their shape -- a timing line, then text up to a blank
    line -- and differ in what else a file may hold."""
    lines = _normalised(text)
    count = len(lines)
    i = 0
    if vtt:
        # The header: `WEBVTT`, optionally with text, and lines up to the
        # first blank one. Its absence is forgiven.
        while i < count and not lines[i].strip():
            i += 1
        if i < count and lines[i].startswith('WEBVTT'):
            while i < count and lines[i].strip():
                i += 1
    while i < count:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        where = f'line {i + 1}'
        if vtt and _VTT_BLOCK.match(line):
            while i < count and lines[i].strip():
                i += 1
            continue
        timing = _timing(line, where)
        if timing is None and i + 1 < count:
            # A cue identifier -- SubRip's number, WebVTT's optional name --
            # on the line before the timing.
            timing = _timing(lines[i + 1], f'line {i + 2}')
            if timing is not None:
                i += 1
                where = f'line {i + 1}'
        if timing is None:
            raise CaptionFormatError(
                f'{where}: expected a cue timing such as '
                f'00:00:01,000 --> 00:00:04,000, found {line.strip()[:60]!r}'
            )
        i += 1
        body = []
        while i < count and lines[i].strip():
            if _timing(lines[i], f'line {i + 1}') is not None:
                # The next cue, with no blank line before it. A SubRip index
                # just above its timing is that cue's, not this one's text.
                if body and _INDEX.match(body[-1]):
                    body.pop()
                    i -= 1
                break
            body.append(lines[i])
            i += 1
        yield timing[0], timing[1], _cue_text(body), where


def _collect(cues) -> Parsed:
    captions, skipped = [], 0
    for start, end, text, where in cues:
        if not text or end <= start:
            skipped += 1
            continue
        try:
            captions.append(Caption(start=start, end=end, text=text))
        except ValidationError as exc:
            reason = exc.errors()[0]['msg']
            raise CaptionFormatError(f'{where}: {reason}') from None
    try:
        return Parsed(captions=checked_captions(captions), skipped=skipped)
    except TooManyCaptions as exc:
        raise CaptionFormatError(str(exc)) from None


def parse_srt(text) -> Parsed:
    """A SubRip (.srt) file's captions."""
    return _collect(_cues(text))


def parse_vtt(text) -> Parsed:
    """A WebVTT (.vtt) file's captions."""
    return _collect(_cues(text, vtt=True))


def _json_time(value, where):
    if isinstance(value, bool):
        raise CaptionFormatError(f'{where}: a time must be seconds, not {value!r}')
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise CaptionFormatError(f'{where}: a time must be a finite number')
        return float(value)
    if isinstance(value, str):
        match = _TIMESTAMP.match(value)
        if match:
            return _seconds(match.groups(), where)
        try:
            return float(value)
        except ValueError:
            pass
    raise CaptionFormatError(
        f'{where}: {value!r} is not a time (seconds, or 00:00:01.000)'
    )


def parse_json(text) -> Parsed:
    """Captions from JSON: a list of `{start, end, text}`, or an object
    holding one under `captions` (as alfred answers), `segments` (as a
    speech engine does) or `cues`. Times are seconds, or timestamps."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    try:
        data = json.loads(str(text).lstrip('﻿'))
    except json.JSONDecodeError as exc:
        raise CaptionFormatError(
            f'line {exc.lineno}: not JSON ({exc.msg.lower()})'
        ) from None
    items = data
    if isinstance(data, dict):
        items = next(
            (
                data[key]
                for key in ('captions', 'segments', 'cues')
                if isinstance(data.get(key), list)
            ),
            None,
        )
    if not isinstance(items, list):
        raise CaptionFormatError(
            'expected a list of {start, end, text}, or an object holding one '
            'under "captions", "segments" or "cues"'
        )

    def cues():
        for number, item in enumerate(items, start=1):
            where = f'caption {number}'
            if not isinstance(item, dict):
                raise CaptionFormatError(f'{where}: expected {{start, end, text}}')
            for key in ('start', 'end'):
                if key not in item:
                    raise CaptionFormatError(f'{where}: no {key}')
            text = item.get('text')
            yield (
                _json_time(item['start'], where),
                _json_time(item['end'], where),
                clean_caption_text(text) if isinstance(text, str) else '',
                where,
            )

    return _collect(cues())


_PARSERS = {'srt': parse_srt, 'vtt': parse_vtt, 'json': parse_json}


def parse(format, text) -> Parsed:
    """The captions in `text`, read as `format`: one of FORMATS."""
    try:
        parser = _PARSERS[format]
    except KeyError:
        raise CaptionFormatError(
            f'{format!r} is not a caption format; use one of {", ".join(FORMATS)}'
        ) from None
    return parser(text)


# --- drawing ----------------------------------------------------------------

# The frame height a style's fontsize is given at; a render at any other
# height scales it.
REFERENCE_HEIGHT = 1080
# A twentieth of the frame's height: 54 pixels at 1080 lines, 36 at 720.
DEFAULT_FONTSIZE = 54
# Below this a caption is not read, whatever the frame.
MIN_PIXELS = 12
# How far the safe area is inset from each edge, as a share of the height.
MARGIN = 0.05
# The widest a caption may be, as a share of the frame; past it, text wraps.
MAX_WIDTH = 0.9
# How wide a glyph is drawn, as a share of the font size, from DejaVu Sans's
# own advance widths: so the box behind a line fits the line rather than
# spanning the frame. An estimate errs one of two ways -- too narrow costs a
# wrapped line, too wide a little air -- so each class takes about its widest
# common member, and anything unlisted counts as wide.
GLYPH_WIDTHS = {
    **dict.fromkeys(' ', 0.32),
    **dict.fromkeys("ijl.,:;!'|`", 0.32),
    **dict.fromkeys('ftrI()[]{}-"/\\', 0.42),
    'm': 0.98,
    'w': 0.82,
    'M': 0.87,
    'W': 0.99,
}
LOWER = 0.64
UPPER = 0.78
OTHER = 0.8


def _glyph_width(char) -> float:
    if char in GLYPH_WIDTHS:
        return GLYPH_WIDTHS[char]
    if unicodedata.east_asian_width(char) in ('W', 'F'):
        return 1.0
    if char.islower():
        return LOWER
    if char.isupper() or char.isdigit():
        return UPPER
    return OTHER


DEFAULT_COLOR = '#ffffff'
# Drawn at the template's own opacity (0.4), so the picture shows through.
DEFAULT_BG = '#000000'
DEFAULT_POSITION = 'bottom'
DEFAULT_ALIGN = 'center'
# A font every image this stack builds has: DejaVu comes with the base image.
DEFAULT_FONT = 'DejaVu-Sans'

# The template every caption is drawn with.
TEMPLATE = 'textBox'


def caption_fontsize(style: CaptionStyle, height) -> int:
    """The size a caption is drawn at in a frame `height` pixels tall."""
    size = style.fontsize or DEFAULT_FONTSIZE
    return max(MIN_PIXELS, round(size * height / REFERENCE_HEIGHT))


def box_width(text, fontsize, frame_width) -> int:
    """How wide to make a caption's box: its longest line, as drawn, plus
    half an em of air on each side -- at most MAX_WIDTH of the frame, where
    the text wraps instead."""
    longest = max(
        (sum(_glyph_width(c) for c in line) for line in text.split('\n')), default=1
    )
    wanted = (longest + 1) * fontsize
    return int(min(max(wanted, fontsize * 2), frame_width * MAX_WIDTH))


def caption_clips(
    captions: Sequence[Caption],
    style: Optional[CaptionStyle],
    size: Tuple[int, int],
    until: Optional[float] = None,
) -> List[dict]:
    """One textBox template clip per caption, for a frame of `size`.

    Nothing when the style is not `enabled`. `until` is where the timeline
    ends, when known: a caption past it is left out and one running over it
    is cut there, so captions never lengthen a render.

    Each clip is drawn inside the frame's safe area -- the clip is the frame
    inset by MARGIN at the top and bottom, placed MARGIN down -- and the
    style's `position` places the caption within that. The box is sized to
    the text (`box_width`) and grows downward as lines wrap; the caption
    method is what wraps them.
    """
    style = style or CaptionStyle()
    if not style.enabled or not captions:
        return []
    width, height = (int(n) for n in size)
    fontsize = caption_fontsize(style, height)
    margin = round(height * MARGIN)
    bg = DEFAULT_BG if style.bg is None else style.bg
    position = style.position or DEFAULT_POSITION
    if isinstance(position, tuple):
        position = list(position)
    clips = []
    # In order of when they start, however they were stored: a later caption
    # is drawn over an earlier one it overlaps.
    for caption in sorted(captions, key=lambda c: (c.start, c.end)):
        start, end = caption.start, caption.end
        if until is not None:
            if start >= until:
                continue
            end = min(end, until)
        length = round(end - start, 3)
        if length <= 0:
            continue
        data = {
            'text': caption.text,
            'fontsize': fontsize,
            'color': style.color or DEFAULT_COLOR,
            'font': style.font or DEFAULT_FONT,
            'align': style.align or DEFAULT_ALIGN,
            'position': position,
            'method': 'caption',
            # A width and no height: the text wraps at the width, and the box
            # is as tall as the lines it took.
            'textsize': [box_width(caption.text, fontsize, width), None],
        }
        if bg:
            data['bg'] = bg
        clips.append(
            {
                'type': 'template',
                'name': TEMPLATE,
                'start': round(start, 3),
                'duration': length,
                'fadeIn': 0,
                'fadeOut': 0,
                'clipsize': [width, max(1, height - 2 * margin)],
                'position': [0, margin],
                'relative': False,
                'data': data,
            }
        )
    return clips


def timeline_end(edl) -> Optional[float]:
    """Where the timeline `edl` ends, in seconds, as the renderer reckons it:
    its `duration` if it states one, else where its last clip ends. None when
    a clip's timing cannot be read -- the render will say why."""
    if edl.duration is not None:
        return edl.duration
    from otto.render import clipTiming

    ends = []
    for clip in edl.clips:
        try:
            timing = clipTiming(clip)
        except Exception:  # noqa: BLE001 - the render reports it, with the clip
            return None
        ends.append(timing.start + timing.length)
    return max(ends) if ends else None


def with_captions(edl: dict, captions, style, size, until=None) -> dict:
    """`edl` (a dict, as a render's payload carries it) with its captions'
    clips after its own, so they are drawn over everything else."""
    clips = caption_clips(captions or [], style, size, until=until)
    if not clips:
        return edl
    return {**edl, 'clips': [*edl.get('clips', []), *clips]}


# --- transcripts ------------------------------------------------------------

# A caption from a transcript is cut where speech would outrun a reader: at
# most two lines of subtitle text, and at most this long on screen.
TRANSCRIPT_CHARS = 84
TRANSCRIPT_SECONDS = 7.0
# A caption this full may end at the end of a sentence rather than run on.
SENTENCE_CHARS = 24
# The shortest a caption from a transcript is shown for.
MIN_SECONDS = 0.3

_SENTENCE_END = re.compile(r'[.!?…]["\')\]]*$')


def _spoken(words) -> str:
    """Words as a line of text. Whisper writes each word with the space
    before it (' Hello', ' world.'); an engine that does not is joined with
    spaces."""
    texts = [w.text for w in words]
    if any(t[:1].isspace() for t in texts[1:]):
        joined = ''.join(texts)
    else:
        joined = ' '.join(t.strip() for t in texts)
    return ' '.join(joined.split())


def _chunks(words):
    chunk = []
    for word in words:
        if chunk:
            text = _spoken(chunk + [word])
            if (
                len(text) > TRANSCRIPT_CHARS
                or word.end - chunk[0].start > TRANSCRIPT_SECONDS
            ):
                yield chunk
                chunk = []
        chunk.append(word)
        spoken = _spoken(chunk)
        if len(spoken) >= SENTENCE_CHARS and _SENTENCE_END.search(spoken):
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _finite(*values) -> bool:
    return all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        for v in values
    )


def captions_from_transcript(segments, until=None) -> List[Caption]:
    """Captions for what an engine heard: `segments` with `start`, `end`,
    `text` and `words` (each with `start`, `end` and `text`), in timeline
    seconds.

    A segment with word timings is cut into readable captions at word
    boundaries (TRANSCRIPT_CHARS, TRANSCRIPT_SECONDS, ends of sentences);
    one without is a caption as it stands. Empty text is dropped, times are
    clamped to the timeline -- from 0 to `until` -- and what is left with no
    length is dropped too.
    """
    pieces = []
    for segment in segments:
        words = [
            w
            for w in (segment.words or ())
            if _finite(w.start, w.end) and w.text.strip()
        ]
        if words:
            for chunk in _chunks(words):
                start, end = chunk[0].start, chunk[-1].end
                if end - start < MIN_SECONDS:
                    end = start + MIN_SECONDS
                pieces.append((start, end, _spoken(chunk)))
        elif _finite(segment.start, segment.end):
            pieces.append((segment.start, segment.end, segment.text))
    captions = []
    for start, end, text in pieces:
        start = max(0.0, start)
        if until is not None:
            if start >= until:
                continue
            end = min(end, until)
        text = clean_caption_text(text)[:MAX_CAPTION_CHARS].strip()
        if not text or end - start <= 0.001:
            continue
        captions.append(Caption(start=start, end=end, text=text))
    # More than a project may carry is a failure that says so, not a
    # transcript quietly cut short.
    return checked_captions(captions)
