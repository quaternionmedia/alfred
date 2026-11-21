"""The language engine, as alfred reaches it -- from here and nowhere else.

otto draws the picture and the audio engine hears the sound. What was said
-- who spoke, which topics were live and when, where the talk went off and
whether it came back -- belongs to a language engine, looksatwords by
default, reached over HTTP by the shape its conversation route takes: a
transcript as lines, `[m:ss] Speaker: words`, answered with the speakers,
the threads of topic over time and the tangents.

This module builds the request from the ALFRED_LANGUAGE_ENGINE_* settings
and reads the answer into alfred's own words. What it offers alfred is what
alfred needs:

- `read(lines)` -- the conversation's speakers, topics and tangents;
- `status()` -- whether there is an engine, and whether it answers;
- `problem()` -- why there is none to use, before anything is sent.

Every failure is a `LanguageEngineError` with one line for a person, naming
the engine: `NoLanguageEngine` (none configured) and `LanguageEngineFailed`
(it could not be reached, broke, or answered nonsense).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpx

from alfred import config

# A failure's line, at most.
REASON_LIMIT = 300

# The route the engine reads a conversation at, and the one that says it is up.
ANALYZE = '/api/conversations/analyze'
HEALTH = '/health'

# Who a line is by when nobody has said: the engine's own word for it.
NOBODY = 'Unknown'


class LanguageEngineError(Exception):
    """The language engine could not do what was asked. The message is one line."""


class NoLanguageEngine(LanguageEngineError):
    """There is no engine to ask: none configured."""


class LanguageEngineFailed(LanguageEngineError):
    """The engine could not be reached, broke, or answered something that is
    not an answer."""


@dataclass(frozen=True)
class Line:
    """One line of the conversation as the engine reads it: who said what,
    from when, in timeline seconds."""

    start: float
    speaker: Optional[str]
    text: str


@dataclass
class Reading:
    """What the engine made of the conversation, in alfred's words."""

    # By name: `{color, contributions}`.
    speakers: Dict[str, dict] = field(default_factory=dict)
    # Each `{name, color, points: [{time, intensity, speaker}]}`, strongest first.
    topics: List[dict] = field(default_factory=list)
    # Each `{start, end, type, topics, text, resolution}`, in order.
    tangents: List[dict] = field(default_factory=list)


@dataclass(frozen=True)
class EngineStatus:
    """`GET /health`'s `language_engine`."""

    configured: bool
    ok: bool
    detail: Optional[str] = None


def engine_url() -> Optional[str]:
    return config.LANGUAGE_ENGINE_URL


def describe(url=None) -> Optional[str]:
    """The engine's address as it may be shown: no credentials, no query."""
    url = url if url is not None else engine_url()
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ''
    if parts.port:
        host = f'{host}:{parts.port}'
    return urlunsplit((parts.scheme, host, parts.path.rstrip('/'), '', ''))


def problem() -> Optional[str]:
    """Why no engine can be asked right now, or None when one can."""
    url = engine_url()
    if not url:
        return (
            'No language engine is configured: set ALFRED_LANGUAGE_ENGINE_URL to '
            "its address (docs/editing-by-text.md says how to run one)."
        )
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return f'ALFRED_LANGUAGE_ENGINE_URL must be an http(s) URL, not {url!r}.'
    return None


def _line(text, url) -> str:
    lines = str(text).strip().splitlines()
    line = lines[0].strip() if lines else ''
    where = describe(url)
    if where and where not in line:
        line = (
            f'the language engine at {where}: {line}'
            if line
            else f'the language engine at {where} failed'
        )
    if len(line) > REASON_LIMIT:
        line = line[: REASON_LIMIT - 3].rstrip() + '...'
    return line


def timecode(seconds: float) -> str:
    whole = int(max(0, seconds))
    return f'{whole // 60}:{whole % 60:02d}'


def transcript_text(lines: Sequence[Line]) -> str:
    """The lines as the engine reads them: `[m:ss] Speaker: words`, one a
    line. A speaker is always written, since the engine splits a line at
    its first colon; a line nobody is named for is `Unknown`, the engine's
    own word."""
    out = []
    for line in lines:
        speaker = (
            ' '.join(str(line.speaker or NOBODY).split()).replace(':', ' ') or NOBODY
        )
        text = ' '.join(str(line.text).split())
        if not text:
            continue
        out.append(f'[{timecode(line.start)}] {speaker}: {text}')
    return '\n'.join(out)


def _number(value, default=0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _reading(answer: dict) -> Reading:
    """The engine's answer in alfred's words. Anything it leaves out is empty."""
    if not isinstance(answer, dict):
        raise LanguageEngineFailed(
            _line('it answered something that is not an answer', engine_url())
        )
    speakers = {}
    for name, info in (answer.get('speakers') or {}).items():
        info = info if isinstance(info, dict) else {}
        speakers[str(name)] = {
            'color': str(info.get('color') or ''),
            'contributions': int(_number(info.get('contributions'), 0)),
        }
    topics = []
    for thread in answer.get('threads') or []:
        if not isinstance(thread, dict):
            continue
        points = []
        for point in thread.get('points') or []:
            if not isinstance(point, dict):
                continue
            points.append(
                {
                    'time': _number(point.get('time')),
                    'intensity': _number(point.get('intensity')),
                    'speaker': str(point.get('speaker') or NOBODY),
                }
            )
        topics.append(
            {
                'name': str(thread.get('name') or ''),
                'color': str(thread.get('color') or ''),
                'points': points,
            }
        )
    tangents = []
    for tangent in answer.get('tangents') or []:
        if not isinstance(tangent, dict):
            continue
        tangents.append(
            {
                'start': _number(tangent.get('start_time')),
                'end': _number(tangent.get('end_time')),
                'type': str(tangent.get('tangent_type') or ''),
                'topics': [str(t) for t in tangent.get('topics') or []],
                'text': str(tangent.get('start_text') or ''),
                'resolution': tangent.get('resolution_text') or None,
            }
        )
    tangents.sort(key=lambda t: t['start'])
    return Reading(speakers=speakers, topics=topics, tangents=tangents)


def _client(transport=None) -> httpx.Client:
    return httpx.Client(
        base_url=engine_url().rstrip('/'),
        timeout=config.LANGUAGE_ENGINE_TIMEOUT,
        transport=transport,
    )


def read(lines: Sequence[Line], title: Optional[str] = None, transport=None) -> Reading:
    """What the engine makes of `lines`: who spoke, which topics were live
    and when, and where the talk went off. `title` names the conversation
    to the engine, which keeps what it read; `transport` is a test's."""
    reason = problem()
    if reason:
        raise NoLanguageEngine(reason)
    text = transcript_text(lines)
    if not text:
        return Reading()
    url = engine_url()
    try:
        with _client(transport) as client:
            response = client.post(
                ANALYZE, json={'text': text, 'title': title or 'alfred'}
            )
    except httpx.HTTPError as exc:
        raise LanguageEngineFailed(_line(f'{type(exc).__name__}: {exc}', url)) from exc
    if response.status_code >= 400:
        raise LanguageEngineFailed(
            _line(f'it answered {response.status_code}: {response.text[:120]}', url)
        )
    try:
        answer = response.json()
    except ValueError as exc:
        raise LanguageEngineFailed(
            _line('it answered something that is not JSON', url)
        ) from exc
    return _reading(answer)


def status(transport=None) -> EngineStatus:
    """Whether an engine is configured, and whether it answers. Blocking."""
    configured = bool(engine_url())
    reason = problem()
    if reason:
        return EngineStatus(configured=configured, ok=False, detail=reason)
    try:
        with _client(transport) as client:
            response = client.get(HEALTH)
        if response.status_code >= 400:
            return EngineStatus(
                True, False, _line(f'it answered {response.status_code}', engine_url())
            )
    except httpx.HTTPError as exc:
        return EngineStatus(
            True, False, _line(f'{type(exc).__name__}: {exc}', engine_url())
        )
    return EngineStatus(configured=True, ok=True)
