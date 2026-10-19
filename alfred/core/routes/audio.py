"""How a library file sounds: the audio engine's analysis of it.

`GET /media/{name}/audio` hands a file from the media library to the audio
engine (`utils.audio_engine`, through vox) and answers what it measured --
tempo, beats, onsets, loudness, silences, a loudness envelope -- for the
editor to cut to. Visible to anyone signed in, as `GET /media` is: the library
is the server's, not one account's.

Answers are kept, by the file's path, modification time and size and the
features asked for, so asking again about an unchanged file costs nothing; a
file that changes is analysed again. The cache is bounded and lives in the
api process.
"""

import os
from typing import Optional

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from alfred import config

from ..errors import Code, Refusal
from ..utils import audio_engine
from ..utils.media import LIBRARY_PREFIX, library_file, media_kind, media_type
from ..utils.probe import ProbeCache

# Analyses kept. One holds a loudness envelope, a few kilobytes for a song.
CACHE_SIZE = 128

# The type a library file is sent to the engine as, where the one it is served
# with will not do. Python's table can spell WAV `audio/x-wav`, which a
# browser plays and an engine reading types strictly refuses; `audio/wav` is
# the name every engine and browser takes.
ENGINE_TYPES = {'.wav': 'audio/wav'}


def engine_type(filename) -> str:
    return ENGINE_TYPES.get(os.path.splitext(filename)[1].lower()) or media_type(
        filename
    )


_cache = ProbeCache(size=CACHE_SIZE)

NOT_IN_LIBRARY = 'No such file in the media library'

audioAPI = APIRouter()


def wanted_features(features: Optional[str]):
    """`features` as a tuple of known names, all of them when none is given;
    422 for one the engine is not asked for (`unknown_feature`)."""
    if not features:
        return audio_engine.FEATURES
    names = tuple(dict.fromkeys(f.strip() for f in features.split(',') if f.strip()))
    unknown = [name for name in names if name not in audio_engine.FEATURES]
    if unknown or not names:
        raise Refusal(
            Code.UNKNOWN_FEATURE,
            f'{", ".join(unknown) or "nothing"}: not a feature; ask for any of '
            f'{", ".join(audio_engine.FEATURES)}',
        )
    return names


@audioAPI.get(
    '/media/{name:path}/audio',
    responses={
        404: {'description': 'no such file in the media library'},
        422: {'description': 'not a file with sound, or not a feature'},
        502: {'description': 'the audio engine failed, and why'},
        503: {'description': 'no audio engine to ask, and why'},
    },
)
async def mediaAudio(name: str, features: Optional[str] = None):
    """# How a library file sounds

    `name` is the file as `GET /media` lists it (`videos/<file>`) or its bare
    file name. `features` is a comma-separated subset of `tempo`, `beats`,
    `onsets`, `loudness`, `silences` and `peaks`; all of them by default.

    Answers the audio engine's analysis: `duration`, `tempo` (beats a minute),
    `beats` and `onsets` (seconds), `loudness` (`rms_db`, `peak_db`, `lufs`),
    `silences` (`[{start, end}]`) and `peaks` (`{rate, values}`, 0 to 1).
    Asked once per version of the file; the answer is kept until it changes.

    503 when no audio engine is configured (`audio_engine_missing`), 502 when
    the engine fails (`audio_engine_failed`), 422 for an image
    (`media_silent`), a file the engine will not read (`audio_engine_refused`)
    or a feature it is not asked for (`unknown_feature`), and 404 for what the
    library does not hold (`not_found`).
    """
    filename = name[len(LIBRARY_PREFIX) :] if name.startswith(LIBRARY_PREFIX) else name
    path = library_file(filename, config.VIDEO_DIR)
    if path is None:
        raise Refusal(Code.NOT_FOUND, NOT_IN_LIBRARY)
    if media_kind(filename) == 'image':
        raise Refusal(
            Code.MEDIA_SILENT,
            f'{LIBRARY_PREFIX}{filename} is an image: it has no sound',
        )
    chosen = wanted_features(features)
    reason = audio_engine.problem()
    if reason:
        raise Refusal(Code.AUDIO_ENGINE_MISSING, reason)

    try:
        stat = os.stat(path)
    except FileNotFoundError:
        raise Refusal(Code.NOT_FOUND, NOT_IN_LIBRARY) from None
    key = (path, stat.st_mtime_ns, stat.st_size, chosen)
    known = _cache.get(key)
    if known is not None:
        return known
    try:
        analysis = await run_in_threadpool(
            audio_engine.analyze, path, engine_type(filename), chosen
        )
    except audio_engine.AudioEngineRefused as exc:
        raise Refusal(Code.AUDIO_ENGINE_REFUSED, str(exc)) from exc
    except audio_engine.NoAudioEngine as exc:
        raise Refusal(Code.AUDIO_ENGINE_MISSING, str(exc)) from exc
    except audio_engine.AudioEngineError as exc:
        raise Refusal(Code.AUDIO_ENGINE_FAILED, str(exc)) from exc
    _cache.put(key, analysis)
    return analysis
