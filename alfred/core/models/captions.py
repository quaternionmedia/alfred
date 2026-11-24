"""Captions on a project, and how they are drawn (contract K2).

A caption is a line of text and the stretch of the timeline it is shown for,
in timeline seconds -- the seconds the editor's playhead counts and the
render's output runs in. `CaptionStyle` is how every caption of a project is
drawn: the fields are the textBox template's own (`utils.captions` maps a
caption onto one), each optional, with `enabled` to keep the captions without
burning them in. `CaptionsJob` is the server's record of the last time the
timeline's sound was sent to the audio engine to be transcribed; `Word` is one
word it heard, kept for editing by text.

What holds for one caption is checked here, wherever a caption arrives: a
start at or after zero, an end after it, and text that says something and
not too much. What holds for a list of them -- in order, and not too many --
is `utils.captions.checked_captions`, applied where a list is written, so a
limit changed later never makes a stored project unreadable.
"""

import math
import re
from datetime import datetime
from typing import Literal, Optional, Tuple, Union

from pydantic import BaseModel, conint, root_validator, validator

# The longest a caption's text may be. Two full subtitle lines are under a
# hundred characters; this is generous, and still bounds what a render has to
# set as type.
MAX_CAPTION_CHARS = 500

# The latest a caption may end, in seconds: a thousand hours, which is every
# time a subtitle file can write with three digits of hours. A bound so that
# a number is a time at all; a caption past the end of its timeline is cut
# when it is drawn.
MAX_CAPTION_SECONDS = 1000 * 3600

# Control characters other than a line break, which a caption may hold: they
# mean nothing on screen and ImageMagick draws some of them as boxes.
_CONTROL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')


def clean_caption_text(text) -> str:
    """`text` as a caption holds it: line breaks normalised, each line's
    whitespace collapsed, blank lines dropped, control characters removed."""
    text = str(text).replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ')
    text = _CONTROL.sub('', text).replace(' ', ' ')
    lines = (' '.join(line.split()) for line in text.split('\n'))
    return '\n'.join(line for line in lines if line)


def timeline_seconds(value, field):
    """`value` as a time on a timeline: finite, not negative, not past
    MAX_CAPTION_SECONDS, and to the millisecond."""
    if not math.isfinite(value):
        raise ValueError(f'{field.name} must be a number of seconds')
    if value < 0:
        raise ValueError(f'{field.name} must not be negative')
    if value > MAX_CAPTION_SECONDS:
        raise ValueError(f'{field.name} must be at most {MAX_CAPTION_SECONDS} seconds')
    # Milliseconds are what any subtitle format can say, and what the
    # editor shows; a float's last digits are noise.
    return round(value, 3)


class Caption(BaseModel):
    """One caption: `text`, shown from `start` until `end`, in timeline seconds."""

    start: float
    end: float
    text: str

    @validator('start', 'end')
    def a_time_on_a_timeline(cls, value, field):
        return timeline_seconds(value, field)

    @validator('text')
    def something_to_read(cls, value):
        text = clean_caption_text(value)
        if not text:
            raise ValueError('a caption needs some text')
        if len(text) > MAX_CAPTION_CHARS:
            raise ValueError(
                f'a caption is at most {MAX_CAPTION_CHARS} characters, '
                f'not {len(text)}'
            )
        return text

    @root_validator(skip_on_failure=True)
    def ends_after_it_starts(cls, values):
        if values['end'] <= values['start']:
            raise ValueError(
                f'a caption must end after it starts '
                f'(start {values["start"]}, end {values["end"]})'
            )
        return values


# Longest word text kept; punctuation is attached to words.
MAX_WORD_CHARS = 100


class Word(BaseModel):
    """One transcript word, in timeline seconds; `end` may equal `start`.
    `segment` numbers its stretch of speech from 0 (a paragraph in the editor)."""

    start: float
    end: float
    text: str
    segment: Optional[conint(ge=0)]

    @validator('start', 'end')
    def a_time_on_a_timeline(cls, value, field):
        return timeline_seconds(value, field)

    @validator('text')
    def one_word(cls, value):
        # One line; drops whisper's leading space.
        text = ' '.join(clean_caption_text(value).split())
        if not text:
            raise ValueError('a word needs some text')
        if len(text) > MAX_WORD_CHARS:
            raise ValueError(
                f'a word is at most {MAX_WORD_CHARS} characters, not {len(text)}'
            )
        return text

    @root_validator(skip_on_failure=True)
    def does_not_end_before_it_starts(cls, values):
        if values['end'] < values['start']:
            raise ValueError(
                f'a word must not end before it starts '
                f'(start {values["start"]}, end {values["end"]})'
            )
        return values


# Where a caption may sit: a word otto places a clip by, or a pair of them --
# left, center or right across, top, center or bottom down. Numbers are not
# offered: a caption is placed inside the frame's safe area
# (`utils.captions`), which numbers would have to know about.
POSITIONS = ('bottom', 'top', 'center')
_ACROSS = ('left', 'center', 'right')
_DOWN = ('top', 'center', 'bottom')

# How the lines of a caption line up with each other, as ImageMagick's
# gravity names them. `left` and `right` are taken as the words people use.
ALIGNMENTS = ('center', 'west', 'east')
_ALIGNMENT_WORDS = {'left': 'west', 'right': 'east', 'centre': 'center'}

# Font names as ImageMagick lists them (`DejaVu-Sans`). Anything else -- a
# path, an `@file` -- is refused: the name goes straight to ImageMagick.
_FONT_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,63}')
_HEX = re.compile(r'#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})')

# A caption's size, in pixels of a frame 1080 pixels tall; scaled to the
# render's own height, so a size chosen once reads the same at every size.
MIN_FONTSIZE = 8
MAX_FONTSIZE = 200


def hex_colour(value) -> str:
    """`#rgb` or `#rrggbb` (with or without the `#`), as `#rrggbb`."""
    match = _HEX.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f'{value!r} is not a colour; use #rrggbb')
    digits = match.group(1).lower()
    if len(digits) == 3:
        digits = ''.join(d * 2 for d in digits)
    return f'#{digits}'


class CaptionStyle(BaseModel):
    """How a project's captions are drawn. Every field may be left out, and
    then the default holds: white text, bottom-centred, on a translucent black
    box, at a twentieth of the frame's height.
    """

    # False keeps the captions without drawing them into renders.
    enabled: bool = True
    # Pixels at 1080 lines (see MIN_FONTSIZE); scaled with the render.
    fontsize: Optional[float]
    color: Optional[str]
    # The box behind the text: a colour, drawn translucent, or '' for none.
    bg: Optional[str]
    position: Optional[Union[str, Tuple[str, str]]]
    align: Optional[str]
    font: Optional[str]

    @validator('fontsize')
    def a_readable_size(cls, value):
        if value is None:
            return value
        if not math.isfinite(value) or not MIN_FONTSIZE <= value <= MAX_FONTSIZE:
            raise ValueError(
                f'fontsize must be between {MIN_FONTSIZE} and {MAX_FONTSIZE} '
                'pixels (at 1080 lines)'
            )
        return value

    @validator('color')
    def a_text_colour(cls, value):
        return None if value is None else hex_colour(value)

    @validator('bg')
    def a_box_colour_or_none(cls, value):
        if value is None:
            return value
        if str(value).strip().lower() in ('', 'none', 'transparent'):
            return ''
        return hex_colour(value)

    @validator('position')
    def a_place_in_the_frame(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            if value in POSITIONS:
                return value
        else:
            across, down = value
            if across in _ACROSS and down in _DOWN:
                return (across, down)
        raise ValueError(
            f'position must be one of {", ".join(POSITIONS)}, or [across, down] '
            f'where across is {"/".join(_ACROSS)} and down {"/".join(_DOWN)}; '
            f'not {value!r}'
        )

    @validator('align')
    def a_known_alignment(cls, value):
        if value is None:
            return value
        word = _ALIGNMENT_WORDS.get(str(value).lower(), str(value).lower())
        if word not in ALIGNMENTS:
            raise ValueError(
                f'align must be one of {", ".join(ALIGNMENTS)} (or left, right)'
            )
        return word

    @validator('font')
    def a_font_name(cls, value):
        if value is None:
            return value
        if not _FONT_NAME.fullmatch(value):
            raise ValueError(
                'font must be a font name such as DejaVu-Sans: letters, digits, '
                'spaces, hyphens and underscores'
            )
        return value


JobState = Literal['queued', 'transcribing', 'done', 'failed']

# The states in which a transcription is still under way.
RUNNING = ('queued', 'transcribing')


class CaptionsJob(BaseModel):
    """The last transcription of a project's timeline: where it got to, and
    -- when it failed -- why, in a line."""

    state: JobState
    error: Optional[str]
    # The engine that was asked: its address, without credentials.
    engine: Optional[str]
    # How many segments of speech the engine heard.
    segments: Optional[int]
    updated_at: Optional[datetime]
