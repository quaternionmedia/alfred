"""What the engines measure of a library file, kept, and of a timeline.

Two measures: how a file sounds, from the audio engine through vox
(`audio_engine.analyze`, the file's sound extracted first for a video,
`sound.file_sound`), and how its picture moves, from otto
(`otto.media.motion`). Each is kept by the file's path, modification time
and size, with what was asked of it, in this process (`probe.ProbeCache`)
and beside the library (`analyses`), so the api's routes and the worker's
jobs read one measure of one file between them.

Everything here is blocking: the extraction, the engine and the decode each
take their time. A route calls it in the thread pool; the worker calls it
as it is. The failures are exceptions with one line for a person, which the
routes answer by code (`routes.audio`, `routes.motion`):

- `NotInLibrary`: no such file;
- `NoSound`: an image, or a video with no sound track;
- `NoPicture`: an image or an audio file, which has no moving picture;
- `PictureUnreadable`: ffmpeg could not read the picture;
- and the audio engine's own, `audio_engine.AudioEngineError` and its kinds.

`timeline_measures` reads a saved timeline's files and maps what was
measured onto the timeline (`sound`), noting each file that could not be
measured rather than failing: a recipe runs over what there is.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from otto.exceptions import FFmpegException
from otto.media import motion as measure_motion

from alfred import config

from . import analyses, audio_engine, sound
from .media import LIBRARY_PREFIX, library_file, media_kind, media_type
from .probe import ProbeCache
from .probe import probe as probe_file

# Measures kept in this process: an hour of material is some kilobytes.
CACHE_SIZE = 128

# Types sent to the engine where the served one will not do: Python may say
# `audio/x-wav`, which a strict engine refuses.
ENGINE_TYPES = {'.wav': 'audio/wav'}

# What a timeline's sound is read for.
SOUND_FEATURES = ('peaks', 'silences')

_sound_cache = ProbeCache(size=CACHE_SIZE)
_motion_cache = ProbeCache(size=CACHE_SIZE)

NOT_IN_LIBRARY = 'No such file in the media library'


class NotInLibrary(LookupError):
    """The library does not hold a file of that name."""


class NoSound(ValueError):
    """The file has no sound to measure: an image, or a video with no sound track."""


class NoPicture(ValueError):
    """The file has no moving picture to measure: an image or an audio file."""


class PictureUnreadable(ValueError):
    """ffmpeg could not read the file's picture. The message ends with what it said."""


def engine_type(filename) -> str:
    return ENGINE_TYPES.get(os.path.splitext(filename)[1].lower()) or media_type(
        filename
    )


def bare_name(name: str) -> str:
    """A library file's name as the library holds it, with or without the
    `videos/` the listing puts in front."""
    return name[len(LIBRARY_PREFIX) :] if name.startswith(LIBRARY_PREFIX) else name


def located(name: str):
    """`(path, filename, kind)` of library file `name`; NotInLibrary otherwise."""
    filename = bare_name(str(name))
    path = library_file(filename, config.VIDEO_DIR)
    if path is None:
        raise NotInLibrary(NOT_IN_LIBRARY)
    return path, filename, media_kind(filename)


def _stat(path):
    try:
        return os.stat(path)
    except FileNotFoundError:
        raise NotInLibrary(NOT_IN_LIBRARY) from None


def _kept(cache, key, make):
    """What is kept under `key` in `cache` or beside the library, else what
    `make` measures, kept in both."""
    known = cache.get(key)
    if known is not None:
        return known
    kept = analyses.get(list(key))
    if kept is not None:
        cache.put(key, kept)
        return kept
    measured = make()
    cache.put(key, measured)
    analyses.put(list(key), measured)
    return measured


def analyse(path, filename, kind, stat, features) -> dict:
    """The engine's analysis of the file, its sound extracted first for a
    video."""
    duration = probe_file(path, kind, stat).duration if kind == 'video' else None
    try:
        with sound.file_sound(path, kind, duration) as (sent, content_type):
            return audio_engine.analyze(
                sent, content_type or engine_type(filename), features
            )
    except sound.NoSoundTrack as exc:
        raise NoSound(str(exc)) from exc


def sound_of(name: str, features: Sequence[str] = SOUND_FEATURES) -> dict:
    """How library file `name` sounds, for `features`, from what is kept when
    the file is unchanged."""
    path, filename, kind = located(name)
    if kind == 'image':
        raise NoSound(f'{LIBRARY_PREFIX}{filename} is an image: it has no sound')
    chosen = tuple(features)
    reason = audio_engine.problem()
    if reason:
        raise audio_engine.NoAudioEngine(reason)
    stat = _stat(path)
    key = (path, stat.st_mtime_ns, stat.st_size, chosen)
    return _kept(_sound_cache, key, lambda: analyse(path, filename, kind, stat, chosen))


def measure(path) -> dict:
    """otto's measure of the picture at `path`, as it is kept and answered."""
    found = measure_motion(path)
    return {'rate': found.rate, 'values': list(found.values)}


def motion_of(name: str) -> dict:
    """How library file `name`'s picture moves, from what is kept when the
    file is unchanged."""
    path, filename, kind = located(name)
    if kind != 'video':
        what = 'an image' if kind == 'image' else 'an audio file'
        raise NoPicture(
            f'{LIBRARY_PREFIX}{filename} is {what}: it has no moving picture'
        )
    stat = _stat(path)
    key = (path, stat.st_mtime_ns, stat.st_size, 'motion')

    def make():
        try:
            return measure(path)
        except (FFmpegException, OSError) as exc:
            raise PictureUnreadable(str(exc)) from exc

    return _kept(_motion_cache, key, make)


def has_picture(clip) -> bool:
    """Whether a clip plays a file whose picture moves: a video."""
    return bool(clip) and clip.get('type') == 'video'


@dataclass
class Measures:
    """What was measured of a timeline, in its own seconds."""

    duration: float
    # `{rate, values}`; None when no file's sound was heard.
    levels: Optional[dict] = None
    # `{rate, values}`; None when no file's picture was measured.
    motion: Optional[dict] = None
    silences: List[dict] = field(default_factory=list)
    # Each file that could not be measured, and why.
    notes: List[str] = field(default_factory=list)


def timeline_measures(clips: Sequence[Optional[dict]]) -> Measures:
    """The sound and the motion of a saved timeline, each file measured once
    and mapped through its clips' windows; a file that cannot be measured is
    a note, and the rest is measured all the same."""
    at = sound.placed(clips)
    measures = Measures(duration=sound.timeline_end(at))
    sounds, pictures = {}, {}
    for a in at:
        name = a['clip'].get('name')
        if sound.sounding(a['clip']) and name not in sounds:
            try:
                sounds[name] = sound_of(str(name))
            except (NotInLibrary, NoSound, audio_engine.AudioEngineError) as exc:
                sounds[name] = None
                measures.notes.append(f'{name}: its sound was not measured: {exc}')
        if has_picture(a['clip']) and name not in pictures:
            try:
                pictures[name] = motion_of(str(name))
            except (NotInLibrary, NoPicture, PictureUnreadable) as exc:
                pictures[name] = None
                measures.notes.append(f'{name}: its motion was not measured: {exc}')
    heard = {name: analysis for name, analysis in sounds.items() if analysis}
    if heard:
        timeline = sound.timeline_sound(clips, heard)
        measures.levels = {'rate': timeline['rate'], 'values': timeline['levels']}
        measures.silences = timeline['silences']
    seen = {name: m for name, m in pictures.items() if m}
    if seen:
        level = sound.levels(at, seen.get, plays=has_picture)
        measures.motion = {'rate': level['rate'], 'values': level['values']}
    return measures
