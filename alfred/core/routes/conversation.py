"""What was said in a project's transcript, as the language engine reads it:
who spoke, which topics were live and when, and where the talk went off.

`GET /project/{id}/conversation` reads the project's stored words;
`POST /project/{id}/conversation` reads the words sent, as they stand in the
editor before a save, so an edit updates the reading. The words are read as
lines, one per stretch of speech, each from its first word's start, said by
the speaker its words name or by nobody (`utils.language_engine`).

Scoped to the caller as every project route is (`utils.ownership`). The
route reaches MongoDB only through the captions routes' `CaptionsStore`,
and the engine only through `utils.language_engine.read`, so a test can
stand in for either. A reading is kept in this process by what was read,
so the same words asked about twice cost one request.
"""

import hashlib
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from ..errors import Code, Refusal
from ..models.captions import Word
from ..utils import language_engine
from ..utils.db import User
from ..utils.language_engine import NOBODY, Line
from ..utils.probe import ProbeCache
from .captions import CaptionsStore, get_captions_store, owned, words_of
from .users import current_active_user

# Readings kept in this process: a long transcript's is some kilobytes.
CACHE_SIZE = 32

# Words with no stretch of speech of their own: a gap this long starts a line.
LINE_GAP = 1.0

_cache = ProbeCache(size=CACHE_SIZE)


class Speaker(BaseModel):
    color: str = ''
    contributions: int = 0


class TopicPoint(BaseModel):
    time: float
    intensity: float
    speaker: str


class Topic(BaseModel):
    name: str
    color: str = ''
    points: List[TopicPoint]


class Tangent(BaseModel):
    start: float
    end: float
    type: str
    topics: List[str] = []
    text: str = ''
    resolution: Optional[str] = None


class LineView(BaseModel):
    start: float
    end: float
    speaker: str
    text: str


class Conversation(BaseModel):
    """`GET` and `POST /project/{id}/conversation`."""

    speakers: Dict[str, Speaker]
    topics: List[Topic]
    tangents: List[Tangent]
    lines: List[LineView]


class WordsSent(BaseModel):
    """`POST /project/{id}/conversation`: the words as they stand."""

    words: List[Word]

    model_config = ConfigDict(extra='forbid')


def lines_of(words: List[Word]) -> List[LineView]:
    """The words as lines: a line per stretch of speech (`segment`), or, for
    words with none, per run of words less than LINE_GAP apart; each from its
    first word's start to its last word's end, said by the speaker its first
    word names, or by nobody."""
    lines: List[LineView] = []
    last: Optional[Word] = None
    for word in sorted(words, key=lambda w: (w.start, w.end)):
        same = last is not None and (
            (word.segment is not None and word.segment == last.segment)
            or (
                word.segment is None
                and last.segment is None
                and word.start - last.end < LINE_GAP
            )
        )
        if same and lines:
            line = lines[-1]
            line.end = max(line.end, word.end)
            line.text = f'{line.text} {word.text}'
        else:
            lines.append(
                LineView(
                    start=word.start,
                    end=word.end,
                    speaker=(word.speaker or NOBODY),
                    text=word.text,
                )
            )
        last = word
    return lines


def _key(lines: List[LineView]) -> str:
    digest = hashlib.sha256(
        json.dumps([[line.start, line.speaker, line.text] for line in lines]).encode()
    ).hexdigest()
    return f'{language_engine.describe()}|{digest}'


async def reading_of(lines: List[LineView], title: Optional[str]) -> Conversation:
    """The engine's reading of `lines`, kept while they do not change."""
    if not lines:
        raise Refusal(
            Code.NO_WORDS,
            'The project has no words to read: transcribe its timeline first.',
        )
    reason = language_engine.problem()
    if reason:
        raise Refusal(Code.LANGUAGE_ENGINE_MISSING, reason)
    key = _key(lines)
    known = _cache.get(key)
    if known is None:
        sent = [
            Line(start=line.start, speaker=line.speaker, text=line.text)
            for line in lines
        ]
        try:
            read = await run_in_threadpool(language_engine.read, sent, title)
        except language_engine.NoLanguageEngine as exc:
            raise Refusal(Code.LANGUAGE_ENGINE_MISSING, str(exc)) from exc
        except language_engine.LanguageEngineError as exc:
            raise Refusal(Code.LANGUAGE_ENGINE_FAILED, str(exc)) from exc
        known = {
            'speakers': read.speakers,
            'topics': read.topics,
            'tangents': read.tangents,
        }
        _cache.put(key, known)
    return Conversation(**known, lines=lines)


conversationAPI = APIRouter()

_RESPONSES = {
    422: {'description': 'the project has no words to read'},
    502: {'description': 'the language engine failed, and why'},
    503: {'description': 'no language engine to ask, and why'},
}


@conversationAPI.get(
    '/project/{item_id}/conversation', response_model=Conversation, responses=_RESPONSES
)
async def getProjectConversation(
    item_id: str,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
):
    """# What was said in a project, as the language engine reads it

    The project's stored words as lines, one per stretch of speech, and what
    the engine made of them: `speakers`, by name, each with the colour the
    engine gave them and how many lines they said; `topics`, each with its
    moments on the timeline and how strongly it was live then; `tangents`,
    where the talk went off and whether it came back. Every time is in
    timeline seconds, to the second.

    422 for a project with no words (`no_words`); 503 when there is no
    language engine (`language_engine_missing`); 502 when it fails
    (`language_engine_failed`).
    """
    project = await owned(store, item_id, user, words=True)
    return await reading_of(lines_of(words_of(project).words), str(project['_id']))


@conversationAPI.post(
    '/project/{item_id}/conversation', response_model=Conversation, responses=_RESPONSES
)
async def readWords(
    item_id: str,
    sent: WordsSent,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
):
    """# What was said, in the words as they stand

    As `GET`, over the `words` sent rather than the stored ones: the editor
    sends what it holds, so a cut, an undo or a speaker named updates the
    reading before a save. Stores nothing.
    """
    project = await owned(store, item_id, user, words=True)
    return await reading_of(lines_of(sent.words), str(project['_id']))
