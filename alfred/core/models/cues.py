"""Cues on a project: moments and stretches of its timeline, each with a label.

A cue is a point or a span in timeline seconds -- the seconds the editor's
playhead counts -- with a label a person reads on the timeline: a chapter, a
stretch proposed as an excerpt, a mark to come back to. `kind` says what sort
of cue it is, `state` where it stands with whoever placed it, `source` who
placed it, so that one writer replaces its own cues and leaves another's where
they are, `ref` the writer's own reference for it -- a request on a queue, a
render -- and `note` what a reader may want to know about it: the words said
in it, how it was chosen. Every field but the times and the label is optional,
and each is a short line.

What holds for one cue is checked here, wherever a cue arrives; what holds for
a list of them -- in order, and not too many -- is `checked_cues`, applied
where a list is written, so a limit changed later never makes a stored
project unreadable.
"""

import re
from typing import Iterable, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from .captions import clean_caption_text, timeline_seconds

# The longest a cue's label, source, reference and note may be.
MAX_LABEL_CHARS = 200
MAX_SOURCE_CHARS = 100
MAX_REF_CHARS = 200
MAX_NOTE_CHARS = 1000

# A kind or a state: a word a program switches on and a stylesheet names.
_WORD = re.compile(r'[a-z][a-z0-9_-]{0,39}')


def one_line(value, name, limit) -> str:
    """`value` as one line of text, its whitespace collapsed, no longer than
    `limit`; '' when it says nothing."""
    text = ' '.join(clean_caption_text(value).split())
    if len(text) > limit:
        raise ValueError(f'a cue {name} is at most {limit} characters, not {len(text)}')
    return text


def a_word(value, name) -> str:
    word = str(value).strip().lower()
    if not _WORD.fullmatch(word):
        raise ValueError(
            f'a cue {name} is a word of letters, digits, hyphens and underscores, '
            f'starting with a letter, at most 40 long; not {value!r}'
        )
    return word


class Cue(BaseModel):
    """One cue: `label`, at `start`, or from `start` until `end`, in timeline
    seconds. A cue with no `end`, or one equal to its start, is a point."""

    start: float
    end: Optional[float] = None
    label: str
    kind: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    ref: Optional[str] = None
    note: Optional[str] = None

    @field_validator('start', 'end')
    @classmethod
    def a_time_on_a_timeline(cls, value, info):
        if value is None:
            return value
        return timeline_seconds(value, info.field_name)

    @field_validator('label')
    @classmethod
    def something_to_read(cls, value):
        text = one_line(value, 'label', MAX_LABEL_CHARS)
        if not text:
            raise ValueError('a cue needs a label')
        return text

    @field_validator('kind', 'state')
    @classmethod
    def a_word_a_program_reads(cls, value, info):
        if value is None or str(value).strip() == '':
            return None
        return a_word(value, info.field_name)

    @field_validator('source')
    @classmethod
    def who_placed_it(cls, value):
        if value is None:
            return value
        return one_line(value, 'source', MAX_SOURCE_CHARS) or None

    @field_validator('ref')
    @classmethod
    def their_reference(cls, value):
        if value is None:
            return value
        return one_line(value, 'ref', MAX_REF_CHARS) or None

    @field_validator('note')
    @classmethod
    def what_to_know(cls, value):
        if value is None:
            return value
        text = clean_caption_text(value)
        if len(text) > MAX_NOTE_CHARS:
            raise ValueError(
                f'a cue note is at most {MAX_NOTE_CHARS} characters, not {len(text)}'
            )
        return text or None

    @model_validator(mode='after')
    def does_not_end_before_it_starts(self):
        if self.end is not None and self.end < self.start:
            raise ValueError(
                f'a cue must not end before it starts (start {self.start}, end {self.end})'
            )
        return self

    @property
    def stop(self) -> float:
        """Where the cue ends: its end, or its start for a point."""
        return self.start if self.end is None else self.end


def checked_cues(cues: Optional[Iterable[Cue]]) -> List[Cue]:
    """`cues` in order of when they start, the earlier-ending first of two that
    start together, however many: what bounds them is the project's document."""
    return sorted(cues or [], key=lambda cue: (cue.start, cue.stop))
