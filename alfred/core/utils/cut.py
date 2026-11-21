"""The cut's arithmetic: a timeline, its captions and its words, cut and
followed, and a span of them as a timeline of its own.

The twin of `website/src/ClipWindow.js`, function for function, over the
plain data a project stores: clips as the editor places them (`start` on the
timeline, `duration`, `inpoint` into the file), captions and words as
`{start, end, text}` in timeline seconds. The two are held equal by the
fixtures under `tests/fixtures/`, which `tests/unit/test_cut.py` and
`website/e2e/cut-fixtures.spec.js` both read: each fixture is a timeline,
its captions and its words, what is done to it, and what comes out.

- `cut_ranges` takes stretches out of every track at once, moves what
  follows up, trims and moves the captions and the words, and rewrites a
  caption's text where it lost words (docs/editing-by-text.md).
- `follow_clips` moves the captions and the words after an edit made with
  the timeline tools, so they stay with the picture they were said over.
- `excerpt` is a span of the timeline as a timeline of its own, beginning at
  0, with its captions and its words moved into it: everything outside the
  span, cut.

Every function is pure: nothing it is given is changed.
"""

import copy
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..models.captions import MAX_CAPTION_CHARS

# The shortest a clip may be made, in seconds (ClipWindow.js SHORTEST).
SHORTEST = 0.1

# otto's default fade for a clip, in seconds, which the API also writes onto
# every clip it stores whether or not anyone chose it (ClipWindow.js).
MODEL_FADE = 1

_MEDIA = frozenset({'video', 'audio'})
_NAN = float('nan')
_MISSING = object()


def to_ms(seconds: float) -> float:
    """Seconds to the millisecond: what is stored, so sums do not drift.
    Rounds a half up, as the browser's `Math.round` does."""
    if not math.isfinite(seconds):
        return seconds
    return math.floor(seconds * 1000 + 0.5) / 1000


def _number(value: Any) -> float:
    """`value` as the browser's `Number` reads it: a number, a numeric string,
    or NaN; None is 0, as `Number(null)` is."""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == '':
            return 0.0
        try:
            return float(text)
        except ValueError:
            return _NAN
    return _NAN


def _field(item: Any, name: str) -> float:
    """`Number(item[name])`: NaN for a field the item does not have."""
    if not isinstance(item, dict) or name not in item:
        return _NAN
    return _number(item[name])


def _or_zero(value: float) -> float:
    """`value || 0`: 0 for NaN."""
    return 0.0 if math.isnan(value) else value


def clip_seconds(clip: Optional[dict]) -> float:
    """Seconds a clip occupies on the timeline."""
    return _or_zero(_field(clip, 'duration')) if clip is not None else 0.0


def in_of(clip: Optional[dict]) -> float:
    """Where in its source a clip starts playing, in seconds."""
    return _or_zero(_field(clip, 'inpoint')) if clip is not None else 0.0


def is_still(clip: Optional[dict]) -> bool:
    """A still picture: a length, but no position in a source to move."""
    return clip is not None and clip.get('type') == 'image'


def windowed(clip: Optional[dict]) -> bool:
    """Whether a clip carries a window its length has to be kept in step with."""
    if clip is None:
        return False
    return (
        clip.get('type') in _MEDIA
        or clip.get('inpoint') is not None
        or clip.get('outpoint') is not None
    )


def place(clip: dict, inpoint: float, length: float) -> dict:
    """Give `clip` its window: start `inpoint` seconds into its source, and
    play for `length` seconds. Writes `duration`, and, for a clip that has a
    window or is given one by starting past 0, `inpoint` and `outpoint` with
    it, so the three always agree. Changes `clip` and returns it."""
    seconds = to_ms(max(0.0, length))
    clip['duration'] = seconds
    still = is_still(clip)
    start_from = to_ms(max(0.0, inpoint))
    if not windowed(clip) and (still or start_from == 0):
        return clip
    # A picture's in-point means nothing; one it already carries is kept.
    start = in_of(clip) if still else start_from
    clip['inpoint'] = start
    clip['outpoint'] = to_ms(start + seconds)
    return clip


def chosen_fade(value: Any) -> float:
    """A clip's fade as it renders: none unless one was chosen, and a fade of
    exactly otto's default is taken as none (ClipWindow.js says why)."""
    if value is None or value == '':
        return 0.0
    seconds = _number(value)
    if not math.isfinite(seconds) or seconds == MODEL_FADE:
        return 0.0
    return max(0.0, seconds)


# --- cutting time out ---------------------------------------------------------


def _start_of(clip: Optional[dict]) -> float:
    """Where a placed clip starts on the output: its `start`, absent as 0."""
    return _or_zero(_field(clip, 'start')) if clip is not None else 0.0


def _present(clips: Optional[Iterable]) -> List[dict]:
    return [clip for clip in (clips or []) if clip is not None]


def timeline_end(clips: Optional[Iterable[dict]]) -> float:
    """Where a timeline of placed clips ends: where the last of them ends."""
    end = 0.0
    for clip in _present(clips):
        end = max(end, _start_of(clip) + clip_seconds(clip))
    return end


def cut_spans(ranges: Optional[Iterable], end: float) -> List[List[float]]:
    """`ranges` clamped to [0, end], to the ms, empty ones dropped, sorted,
    overlaps merged. A range is `[start, end]` or `{start, end}`."""
    spans = []
    limit = _or_zero(_number(end))
    for item in ranges or []:
        if isinstance(item, (list, tuple)):
            a = item[0] if len(item) > 0 else None
            b = item[1] if len(item) > 1 else None
            a = _NAN if a is None else _number(a)
            b = _NAN if b is None else _number(b)
        else:
            a = _field(item, 'start')
            b = _field(item, 'end')
        if not math.isfinite(a) or not math.isfinite(b):
            continue
        start = to_ms(max(0.0, a))
        stop = to_ms(min(limit, b))
        if to_ms(stop - start) <= 0:
            continue
        spans.append([start, stop])
    spans.sort(key=lambda span: span[0])
    merged: List[List[float]] = []
    for start, stop in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], stop)
        else:
            merged.append([start, stop])
    return merged


def _cut_before(t: float, spans: Sequence[Sequence[float]]) -> float:
    """How many seconds of `spans` lie before `t`."""
    return sum(max(0.0, min(t, stop) - start) for start, stop in spans)


def _moved(t: float, spans: Sequence[Sequence[float]]) -> float:
    """Where second `t` lands once `spans` are cut; inside a span, at its start."""
    return to_ms(t - _cut_before(t, spans))


def _outside(start: float, stop: float, spans: Sequence[Sequence[float]]) -> list:
    """The stretches of `[start, stop)` outside every span."""
    parts = []
    at = start
    for a, b in spans:
        if b <= at:
            continue
        if a >= stop:
            break
        if a > at:
            parts.append([at, a])
        at = max(at, b)
        if at >= stop:
            break
    if at < stop:
        parts.append([at, stop])
    return [[a, b] for a, b in parts if to_ms(b - a) > 0]


def _copy(clip: dict) -> dict:
    """A copy of a clip, settings and all, without the view's index."""
    copied = copy.deepcopy(clip)
    copied.pop('i', None)
    return copied


def _times_of(item: dict) -> Optional[List[float]]:
    """An item's times as numbers, or None while one is not (a caption being
    typed, its field empty or missing)."""
    start = _NAN if item.get('start', _MISSING) == '' else _field(item, 'start')
    end = _NAN if item.get('end', _MISSING) == '' else _field(item, 'end')
    if math.isfinite(start) and math.isfinite(end):
        return [start, end]
    return None


def _at(item: dict, start: float, end: float) -> dict:
    """`item` at `[start, end]`: itself when that is where it is."""
    if _field(item, 'start') == start and _field(item, 'end') == end:
        return item
    return {**item, 'start': start, 'end': end}


def after_cut(item: dict, spans: Sequence[Sequence[float]]) -> Optional[dict]:
    """A caption or word after the cut: moved and trimmed, or None when
    nothing is left. Zero-length: gone if inside a span, edges included.
    Non-numeric times: left as is."""
    times = _times_of(item)
    if times is None:
        return item
    start, end = times
    if end == start and any(a <= start <= b for a, b in spans):
        return None
    moved_start = _moved(start, spans)
    moved_end = _moved(end, spans)
    if end > start and to_ms(moved_end - moved_start) <= 0:
        return None
    return _at(item, moved_start, moved_end)


# --- a caption's words ----------------------------------------------------------


def _middle(times: Sequence[float]) -> float:
    return (times[0] + times[1]) / 2


def retext(
    captions: Optional[Sequence[dict]],
    moved: Sequence[Optional[dict]],
    words: Optional[Sequence[dict]],
    kept: Sequence[Optional[dict]],
) -> List[Optional[dict]]:
    """Captions after an edit, their text rewritten where they lost words.
    `captions[i]` became `moved[i]`, `words[j]` became `kept[j]`; None is
    gone. A caption's words: those whose middle lies in it. Lost some: says
    the rest, by spaces. Lost all: None. Lost none, or held none: as moved.
    Rules: docs/captions.md, "Editing by text"."""
    order = []
    for j, word in enumerate(words or []):
        times = _times_of(word)
        if times is not None:
            order.append((_middle(times), j))
    order.sort(key=lambda entry: entry[0])

    def first_from(t: float) -> int:
        lo, hi = 0, len(order)
        while lo < hi:
            mid = (lo + hi) >> 1
            if order[mid][0] < t:
                lo = mid + 1
            else:
                hi = mid
        return lo

    out: List[Optional[dict]] = []
    for i, caption in enumerate(captions or []):
        after = moved[i]
        times = _times_of(caption)
        if after is None or times is None:
            out.append(after)
            continue
        members = []
        k = first_from(times[0])
        while k < len(order) and order[k][0] <= times[1]:
            members.append(order[k][1])
            k += 1
        if not members:
            out.append(after)
            continue
        span = _times_of(after)
        # Survived, and still under the caption (a move can take a word elsewhere).
        left = []
        for j in members:
            word = kept[j]
            word_times = _times_of(word) if word is not None else None
            if (
                word_times is not None
                and span is not None
                and word_times[0] <= span[1]
                and word_times[1] >= span[0]
            ):
                left.append(j)
        if len(left) == len(members):
            out.append(after)
            continue
        if not left:
            out.append(None)
            continue
        left.sort(key=lambda j: (_field(kept[j], 'start'), j))
        text = ' '.join(str(kept[j]['text']).strip() for j in left)
        out.append({**after, 'text': text[:MAX_CAPTION_CHARS].strip()})
    return out


def cut_ranges(timeline: Optional[dict], ranges: Optional[Iterable]) -> dict:
    """Cut `ranges` (`[start, end]` pairs, any order) out of
    `{clips, captions, words}`. Clips are placed by `start`, on any number of
    tracks. Returns `{clips, captions, words, removed, spans}`."""
    timeline = timeline or {}
    present = _present(timeline.get('clips'))
    spans = cut_spans(ranges, timeline_end(present))
    removed = to_ms(sum(b - a for a, b in spans))
    kept = []
    for clip in present:
        start = _start_of(clip)
        length = clip_seconds(clip)
        end = start + length
        parts = _outside(start, end, spans) if length > 0 else [[start, start]]
        # Untouched: same clip, moved.
        if len(parts) == 1 and parts[0][0] == start and parts[0][1] == end:
            kept.append({**_copy(clip), 'start': _moved(start, spans)})
            continue
        for part_start, part_end in parts:
            part = _copy(clip)
            place(
                part,
                in_of(clip) if is_still(clip) else in_of(clip) + (part_start - start),
                part_end - part_start,
            )
            part['start'] = _moved(part_start, spans)
            # Hard edit at a cut.
            if part_start > start:
                part['fadeIn'] = 0
            if part_end < end:
                part['fadeOut'] = 0
            kept.append(part)

    def cut(items):
        return [after_cut(item, spans) for item in (items or [])]

    words = timeline.get('words') or []
    captions = timeline.get('captions') or []
    kept_words = cut(words)
    kept_captions = retext(captions, cut(captions), words, kept_words)
    return {
        'clips': kept,
        'captions': [c for c in kept_captions if c is not None],
        'words': [w for w in kept_words if w is not None],
        'removed': removed,
        'spans': spans,
    }


# --- following an edit made with the timeline tools -------------------------------


def _window_of(clip: dict) -> dict:
    """A placed clip's window: where it starts, where in its source, and for
    how long."""
    return {'start': _start_of(clip), 'from': in_of(clip), 'length': clip_seconds(clip)}


def _kept_pieces(before: Sequence[dict], after: Sequence[dict]) -> List[dict]:
    """What an edit kept of the timeline: `{from, to, at, place}`, old
    [from, to) now starting at `at`, in the edited timeline's clip `place`.
    Lineage by `key`; the common part of a clip's source windows is what it
    kept. Past the old end: left where it is."""
    places: Dict[Any, int] = {}
    for n, clip in enumerate(after):
        places[clip.get('key')] = n
    pieces = []
    for clip in before:
        key = clip.get('key')
        if key is None or key not in places:
            continue
        n = places[key]
        was = _window_of(clip)
        now = _window_of(after[n])
        lo = max(was['from'], now['from'])
        hi = min(was['from'] + was['length'], now['from'] + now['length'])
        if to_ms(hi - lo) <= 0:
            continue
        pieces.append(
            {
                'from': was['start'] + lo - was['from'],
                'to': was['start'] + hi - was['from'],
                'at': now['start'] + lo - now['from'],
                'place': n,
            }
        )
    end = timeline_end(before)
    pieces.append({'from': end, 'to': math.inf, 'at': end, 'place': len(after)})
    pieces.sort(key=lambda piece: piece['from'])
    return pieces


def _through(item: dict, pieces: Sequence[dict]) -> Optional[dict]:
    """A caption or word through `pieces`: None when none of it was kept.
    Its parts that still follow each other, in the same or neighbouring
    clips, stay one; else it keeps its longest such run. A moment goes with
    the piece holding it. Non-numeric: as is."""
    times = _times_of(item)
    if times is None:
        return item
    start, end = times
    if end <= start:
        piece = next((p for p in pieces if p['from'] <= start < p['to']), None)
        if piece is None:
            return None
        t = to_ms(piece['at'] + start - piece['from'])
        return _at(item, t, t)
    best = None
    run = None
    for p in pieces:
        if p['to'] <= start or p['from'] >= end:
            continue
        a = p['at'] + max(start, p['from']) - p['from']
        b = p['at'] + min(end, p['to']) - p['from']
        if to_ms(b - a) <= 0:
            continue
        follows = (
            run is not None
            and a >= run['end'] - 0.0005
            and (p['place'] == run['place'] or p['place'] == run['place'] + 1)
        )
        if follows:
            run['end'] = b
            run['place'] = p['place']
            run['length'] += b - a
        else:
            run = {'start': a, 'end': b, 'place': p['place'], 'length': b - a}
        # To the ms: a tie is a tie, and the first said wins it.
        if best is None or to_ms(run['length']) > to_ms(best['length']):
            best = run
    if best is None:
        return None
    return _at(item, to_ms(best['start']), to_ms(best['end']))


def follow_clips(edit: Optional[dict]) -> dict:
    """Captions and words after an edit with the timeline tools: they follow
    the picture. `edit` is `{before, after, captions, words}`: placed clips
    (`start`, `duration`, `inpoint`, `type`), each with a `key` naming the
    clip it is, the same before and after; a clip with no partner is new, or
    gone. Returns `{captions, words}`, words in timeline order, captions in
    the order given. Rules: docs/captions.md, "Words follow the picture"."""
    edit = edit or {}

    def placed(clips):
        return sorted(_present(clips), key=_start_of)

    pieces = _kept_pieces(placed(edit.get('before')), placed(edit.get('after')))
    words = edit.get('words') or []
    captions = edit.get('captions') or []
    kept_words = [_through(word, pieces) for word in words]
    kept_captions = retext(
        captions, [_through(caption, pieces) for caption in captions], words, kept_words
    )
    # A move can put later speech first; stable, so equal starts keep their order.
    ordered = sorted(
        ((word, j) for j, word in enumerate(kept_words) if word is not None),
        key=lambda entry: (_field(entry[0], 'start'), entry[1]),
    )
    return {
        'captions': [c for c in kept_captions if c is not None],
        'words': [word for word, _ in ordered],
    }


# --- a span as a timeline of its own ---------------------------------------------


class NothingToExcerpt(ValueError):
    """The span holds nothing of the timeline. The message says which span."""


def excerpt(timeline: Optional[dict], start: float, end: float) -> dict:
    """The part of `{clips, captions, words}` between `start` and `end`, in
    timeline seconds, as a timeline of its own that begins at 0: everything
    outside the span cut, by `cut_ranges`, so each clip keeps every field it
    had, an edge the span cut has no fade, the captions and the words are
    moved into it and a caption that lost words says the ones it has left.
    The span is held to the timeline's end. Returns `{clips, duration,
    captions, words}`; NothingToExcerpt when no clip plays in the span."""
    timeline = timeline or {}
    until = timeline_end(timeline.get('clips'))
    span = cut_spans([[start, end]], until)
    if not span:
        raise NothingToExcerpt(f'nothing to cut between {start} and {end} seconds')
    [[from_, to]] = span
    cut = cut_ranges(timeline, [[0, from_], [to, until]])
    if not cut['clips']:
        raise NothingToExcerpt(
            f'no clip of the timeline plays between {start} and {end} seconds'
        )
    return {
        'clips': cut['clips'],
        'duration': to_ms(to - from_),
        'captions': cut['captions'],
        'words': cut['words'],
    }
