"""How a library file sounds: the audio engine's analysis of it.

`GET /media/{name}/audio` hands the sound of a file from the media library to
the audio engine (`utils.audio_engine`, through vox) and answers what it
measured -- tempo, beats, onsets, loudness, silences, a loudness envelope --
for the editor to cut to. Visible to anyone signed in, as `GET /media` is: the
library is the server's, not one account's.

An audio file goes to the engine as it is. A video's sound goes alone, as a
WAV otto writes from it (`utils.sound.file_sound`): the engine is asked about
the sound, and a long recording's picture is most of its bytes, more than an
engine takes in one upload.

Answers are kept, by the file's path, modification time and size and the
features asked for, so asking again about an unchanged file costs nothing; a
file that changes is analysed again. The answer is kept in this process and
beside the library (`utils.analyses`), where the worker and an api that has
restarted read it. `library_analysis` is the whole of it, for the routes that
read a timeline's sound through the files it plays.
"""

import os
from typing import Optional, Sequence

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from alfred import config

from ..errors import Code, Refusal
from ..utils import analyses, audio_engine, sound
from ..utils.media import LIBRARY_PREFIX, library_file, media_kind, media_type
from ..utils.probe import ProbeCache
from ..utils.probe import probe as probe_file

# Analyses kept in this process. One holds a loudness envelope, a few
# kilobytes for a song.
CACHE_SIZE = 128

# Types sent to the engine where the served one will not do: Python may say
# `audio/x-wav`, which a strict engine refuses.
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


def bare_name(name: str) -> str:
    """A library file's name as the library holds it, with or without the
    `videos/` the listing puts in front."""
    return name[len(LIBRARY_PREFIX) :] if name.startswith(LIBRARY_PREFIX) else name


def analyse(path, filename, kind, stat, features) -> dict:
    """The engine's analysis of the file, its sound extracted first for a
    video. Blocking: the extraction and the engine both take their time."""
    duration = probe_file(path, kind, stat).duration if kind == 'video' else None
    try:
        with sound.file_sound(path, kind, duration) as (sent, content_type):
            return audio_engine.analyze(
                sent, content_type or engine_type(filename), features
            )
    except sound.NoSoundTrack as exc:
        raise Refusal(Code.MEDIA_SILENT, str(exc)) from exc
    except audio_engine.AudioEngineRefused as exc:
        raise Refusal(Code.AUDIO_ENGINE_REFUSED, str(exc)) from exc
    except audio_engine.NoAudioEngine as exc:
        raise Refusal(Code.AUDIO_ENGINE_MISSING, str(exc)) from exc
    except audio_engine.AudioEngineError as exc:
        raise Refusal(Code.AUDIO_ENGINE_FAILED, str(exc)) from exc


async def library_analysis(name: str, features: Sequence[str]) -> dict:
    """The engine's analysis of library file `name` for `features`, from
    what is kept when the file is unchanged. Its refusals are the route's:
    404 for a file the library does not hold, 422 for an image or a video
    with no sound track, 503 for no engine, 502 when the engine fails."""
    filename = bare_name(name)
    path = library_file(filename, config.VIDEO_DIR)
    if path is None:
        raise Refusal(Code.NOT_FOUND, NOT_IN_LIBRARY)
    kind = media_kind(filename)
    if kind == 'image':
        raise Refusal(
            Code.MEDIA_SILENT,
            f'{LIBRARY_PREFIX}{filename} is an image: it has no sound',
        )
    chosen = tuple(features)
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
    kept = await run_in_threadpool(analyses.get, list(key))
    if kept is not None:
        _cache.put(key, kept)
        return kept
    analysis = await run_in_threadpool(analyse, path, filename, kind, stat, chosen)
    _cache.put(key, analysis)
    await run_in_threadpool(analyses.put, list(key), analysis)
    return analysis


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
    An audio file is sent as it is; a video's sound is sent alone, as a mono
    WAV at 16 kHz. Asked once per version of the file; the answer is kept
    until it changes.

    503 when no audio engine is configured (`audio_engine_missing`), 502 when
    the engine fails (`audio_engine_failed`), 422 for an image or a video
    with no sound track (`media_silent`), a file the engine will not read
    (`audio_engine_refused`) or a feature it is not asked for
    (`unknown_feature`), and 404 for what the library does not hold
    (`not_found`).
    """
    return await library_analysis(name, wanted_features(features))
