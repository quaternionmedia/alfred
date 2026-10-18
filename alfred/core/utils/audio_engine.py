"""The audio engine, as alfred reaches it -- from here and nowhere else.

otto draws the picture. The sound -- what a timeline says, how a library file
sounds -- belongs to an audio engine (joe, by default), driven through vox:
QM's seam for one, vendored at `alfred/vox` beside `alfred/otto`. vox states
what an engine must answer as a value, `EngineContract`, whose defaults are
one engine's spelling, and its media client, `vox.media.MediaEngine`, drives
any engine that answers one.

This module builds that value from the ALFRED_AUDIO_ENGINE_* settings and is
the only part of alfred that imports vox. It names no path, parameter or
response key of any engine's: those are the contract's, overridden field by
field from the environment (`config.AUDIO_ENGINE_CONTRACT`), so pointing
alfred at an engine that spells things differently is configuration, not
code. What it offers alfred is what alfred needs:

- `transcribe(path)` -- what a file says, as segments with word timings;
- `analyze(path, content_type, features)` -- how a file sounds;
- `status()` -- whether there is an engine, and whether it answers;
- `problem()` -- why there is none to use, before anything is queued.

Every failure is an `AudioEngineError` with one line for a person, naming the
engine: `NoAudioEngine` (none configured, or none reachable from this build),
`AudioEngineRefused` (the engine would not take this input) and
`AudioEngineFailed` (it could not be reached, broke, or answered nonsense).
"""

import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from alfred import config

# What `GET /media/{name}/audio` may ask the engine to measure, all of them by
# default.
FEATURES = ('tempo', 'beats', 'onsets', 'loudness', 'silence', 'peaks')

# A failure's line, at most.
REASON_LIMIT = 300


class AudioEngineError(Exception):
    """The audio engine could not do what was asked. The message is one line."""


class NoAudioEngine(AudioEngineError):
    """There is no engine to ask: none configured, or none this build can reach."""


class AudioEngineRefused(AudioEngineError):
    """The engine would not take this input -- a file with no sound, a type it
    does not read, one too large."""


class AudioEngineFailed(AudioEngineError):
    """The engine could not be reached, broke, or answered something that is
    not an answer."""


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str
    probability: Optional[float] = None


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    words: Tuple[Word, ...] = ()


@dataclass(frozen=True)
class Transcript:
    """What an engine heard, in seconds of the file it was given."""

    segments: Tuple[Segment, ...]
    language: Optional[str] = None
    text: str = ''


@dataclass(frozen=True)
class EngineStatus:
    """`GET /health`'s `audio_engine`: whether there is one, and whether it
    answers; `detail` says why not when it does not."""

    configured: bool
    ok: bool
    detail: Optional[str] = None


# --- configuration ----------------------------------------------------------


def _vox_media():
    """vox's media client. The one import of it in alfred.

    vox's main branch does not carry it yet (it lands with vox's media
    engine work); until the vendored copy does, `problem()` says so and
    nothing is sent anywhere.
    """
    from vox import media

    return media


def engine_url() -> Optional[str]:
    return config.AUDIO_ENGINE_URL


def describe(url=None) -> Optional[str]:
    """The engine's address as it may be shown and stored: no credentials,
    no query."""
    url = url if url is not None else engine_url()
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ''
    if parts.port:
        host = f'{host}:{parts.port}'
    return urlunsplit((parts.scheme, host, parts.path.rstrip('/'), '', ''))


def contract(overrides=None):
    """vox's `EngineContract`: its defaults, with `overrides` -- by default
    `config.AUDIO_ENGINE_CONTRACT` -- in place of the fields they name.
    NoAudioEngine for a name that is not one of its fields."""
    from vox.contract import EngineContract

    overrides = config.AUDIO_ENGINE_CONTRACT if overrides is None else overrides
    known = {field.name for field in dataclasses.fields(EngineContract)}
    unknown = sorted(set(overrides) - known)
    if unknown:
        names = ', '.join(
            f'{config.AUDIO_ENGINE_CONTRACT_PREFIX}{name.upper()}' for name in unknown
        )
        raise NoAudioEngine(
            f"{names}: not a field of vox's EngineContract, so not something an "
            f'engine can be told to spell differently; the fields are '
            f'{", ".join(sorted(known))}'
        )
    return EngineContract(**overrides)


def problem() -> Optional[str]:
    """Why no engine can be asked right now, or None when one can.

    Configuration and this build only -- whether the engine answers is
    `status()`'s question, and costs a request.
    """
    url = engine_url()
    if not url:
        return (
            'No audio engine is configured: set ALFRED_AUDIO_ENGINE_URL to its '
            'address (docs/captions.md says how to run one).'
        )
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return f'ALFRED_AUDIO_ENGINE_URL must be an http(s) URL, not {url!r}.'
    try:
        _vox_media()
    except ImportError:
        return (
            'The vendored vox (alfred/vox) has no media client (vox.media), so '
            f'the audio engine at {describe(url)} cannot be asked anything.'
        )
    try:
        contract()
    except NoAudioEngine as exc:
        return str(exc)
    return None


# --- talking to it ----------------------------------------------------------


def _line(text, url) -> str:
    lines = str(text).strip().splitlines()
    line = lines[0].strip() if lines else ''
    where = describe(url)
    if where and where not in line:
        line = (
            f'the audio engine at {where}: {line}'
            if line
            else (f'the audio engine at {where} failed')
        )
    if len(line) > REASON_LIMIT:
        line = line[: REASON_LIMIT - 3].rstrip() + '...'
    return line


def _status_of(exc) -> Optional[int]:
    status = getattr(exc, 'status', None)
    if status is None and exc.args and isinstance(exc.args[0], int):
        status = exc.args[0]
    return status if isinstance(status, int) else None


def _detail_of(exc) -> str:
    detail = getattr(exc, 'detail', None)
    if detail is None:
        detail = exc.args[1] if len(exc.args) > 1 else str(exc)
    return str(detail)


def _call(media, url, method, *args, **kwargs):
    """`method(*args, **kwargs)`, its failures as AudioEngineErrors."""
    refused = getattr(media, 'EngineRefused', ())
    try:
        return method(*args, **kwargs)
    except AudioEngineError:
        raise
    except refused as exc:
        status = _status_of(exc)
        detail = _detail_of(exc)
        if status is not None and 400 <= status < 500:
            raise AudioEngineRefused(
                _line(f'it refused this ({status}): {detail}', url)
            ) from exc
        raise AudioEngineFailed(
            _line(f'it failed ({status or "no status"}): {detail}', url)
        ) from exc
    except Exception as exc:  # noqa: BLE001 - unavailable, malformed, or worse
        message = str(exc) or type(exc).__name__
        known = tuple(
            getattr(media, name)
            for name in ('EngineUnavailable', 'EngineAnswerMalformed')
            if isinstance(getattr(media, name, None), type)
        )
        if not isinstance(exc, known):
            message = f'{type(exc).__name__}: {message}'
        raise AudioEngineFailed(_line(message, url)) from exc


@contextmanager
def _engine():
    """A connected `MediaEngine` for the configured engine, closed after."""
    reason = problem()
    if reason:
        raise NoAudioEngine(reason)
    media = _vox_media()
    url = engine_url()
    engine = media.MediaEngine(
        contract=contract(), base_url=url, timeout=config.AUDIO_ENGINE_TIMEOUT
    )
    if hasattr(engine, '__enter__'):
        with engine:
            yield media, url, engine
    else:
        yield media, url, engine


def _forget(engine, handle) -> None:
    """Ask the engine to drop what was uploaded; it expires anyway."""
    try:
        engine.close(handle)
    except Exception as exc:  # noqa: BLE001 - housekeeping
        print('the audio engine did not drop an upload:', exc, flush=True)


@contextmanager
def _uploaded(media, url, engine, path, content_type):
    handle = _call(media, url, engine.upload, str(path), content_type)
    try:
        yield handle
    finally:
        _forget(engine, handle)


def _get(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _number(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _transcript(answer) -> Transcript:
    segments = []
    for segment in _get(answer, 'segments') or ():
        words = []
        for word in _get(segment, 'words') or ():
            start, end = _number(_get(word, 'start')), _number(_get(word, 'end'))
            text = _get(word, 'word', _get(word, 'text'))
            if start is None or end is None or not isinstance(text, str):
                continue
            words.append(Word(start, end, text, _number(_get(word, 'probability'))))
        start, end = _number(_get(segment, 'start')), _number(_get(segment, 'end'))
        if start is None or end is None:
            continue
        text = _get(segment, 'text')
        segments.append(
            Segment(start, end, text if isinstance(text, str) else '', tuple(words))
        )
    language = _get(answer, 'language')
    text = _get(answer, 'text')
    return Transcript(
        segments=tuple(segments),
        language=language if isinstance(language, str) else None,
        text=text if isinstance(text, str) else '',
    )


def _plain(answer):
    """An answer as JSON-ready data, whether vox gave a dataclass or a dict."""
    if dataclasses.is_dataclass(answer) and not isinstance(answer, type):
        return dataclasses.asdict(answer)
    if isinstance(answer, dict):
        return dict(answer)
    raise AudioEngineFailed(
        _line(f'it answered {type(answer).__name__}, not an analysis', engine_url())
    )


def transcribe(path, content_type='audio/wav', language=None) -> Transcript:
    """What the audio file at `path` says, with word timings where the engine
    gives them. Times are seconds of that file."""
    with _engine() as (media, url, engine):
        with _uploaded(media, url, engine, path, content_type) as handle:
            answer = _call(
                media, url, engine.transcribe, handle, language=language, words=True
            )
    return _transcript(answer)


def analyze(path, content_type, features: Sequence[str] = FEATURES) -> dict:
    """How the file at `path` sounds: the engine's analysis, for `features`."""
    with _engine() as (media, url, engine):
        with _uploaded(media, url, engine, path, content_type) as handle:
            answer = _call(media, url, engine.analyze, handle, list(features))
    return _plain(answer)


def capabilities() -> dict:
    """What the engine says it can do."""
    with _engine() as (media, url, engine):
        answer = _call(media, url, engine.capabilities)
    return _plain(answer)


def status() -> EngineStatus:
    """Whether an engine is configured, and whether it answers. Blocking: it
    asks the engine what it can do."""
    configured = bool(engine_url())
    reason = problem()
    if reason:
        return EngineStatus(configured=configured, ok=False, detail=reason)
    try:
        capabilities()
    except AudioEngineError as exc:
        return EngineStatus(configured=True, ok=False, detail=str(exc))
    return EngineStatus(configured=True, ok=True)
