"""How a library file sounds: the audio engine's analysis of it.

`GET /media/{name}/audio` hands the sound of a file from the media library to
the audio engine (`utils.measures.sound_of`, through `utils.audio_engine` and
vox) and answers what it measured -- tempo, beats, onsets, loudness,
silences, a loudness envelope -- for the editor to cut to. Visible to anyone
signed in, as `GET /media` is: the library is the server's, not one
account's.

An audio file goes to the engine as it is. A video's sound goes alone, as a
WAV otto writes from it: the engine is asked about the sound, and a long
recording's picture is most of its bytes, more than an engine takes in one
upload. Answers are kept per version of the file, in this process and beside
the library, so asking again about an unchanged file costs nothing.
`library_analysis` is the whole of it, for the routes that read a timeline's
sound through the files it plays.
"""

from typing import Optional, Sequence

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..errors import Code, Refusal
from ..utils import audio_engine, measures

audioAPI = APIRouter()


def wanted_features(features: Optional[str]):
    """`features` as a tuple of known names, all of them when none is given;
    422 for one the engine is not asked for (`unknown_feature`)."""
    if not features:
        return audio_engine.FEATURES
    names = tuple(dict.fromkeys(f.strip() for f in features.split(',') if f.strip()))
    unknown = [name for name in names if name not in audio_engine.KNOWN_FEATURES]
    if unknown or not names:
        raise Refusal(
            Code.UNKNOWN_FEATURE,
            f'{", ".join(unknown) or "nothing"}: not a feature; ask for any of '
            f'{", ".join(audio_engine.KNOWN_FEATURES)}',
        )
    return names


async def library_analysis(name: str, features: Sequence[str]) -> dict:
    """The engine's analysis of library file `name` for `features`, from
    what is kept when the file is unchanged, each failure a refusal by code:
    404 for a file the library does not hold, 422 for an image or a video
    with no sound track, 503 for no engine, 502 when the engine fails."""
    try:
        return await run_in_threadpool(measures.sound_of, name, tuple(features))
    except measures.NotInLibrary as exc:
        raise Refusal(Code.NOT_FOUND, str(exc)) from exc
    except measures.NoSound as exc:
        raise Refusal(Code.MEDIA_SILENT, str(exc)) from exc
    except audio_engine.AudioEngineRefused as exc:
        raise Refusal(Code.AUDIO_ENGINE_REFUSED, str(exc)) from exc
    except audio_engine.NoAudioEngine as exc:
        raise Refusal(Code.AUDIO_ENGINE_MISSING, str(exc)) from exc
    except audio_engine.AudioEngineError as exc:
        raise Refusal(Code.AUDIO_ENGINE_FAILED, str(exc)) from exc


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
