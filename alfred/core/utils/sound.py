"""The sound of a timeline, in its own seconds.

The audio engine measures a file: `peaks`, its level so many times a second,
and `silences`, in the file's seconds. A clip plays a window of a file at a
place on the timeline. This module maps what was measured onto the timeline,
as the editor's Audio lane does in the browser (`website/src/lanes/arith.js`,
`placed` and `silences`; the fixtures under `tests/fixtures/sound/` hold the
two equal), and gives the whole timeline one level over time, where the
clips that sound at once are heard together as the loudest of them.

It also says how a library file's sound reaches the engine: an audio file as
it is, and a video's sound alone, as a WAV otto writes
(`otto.render.renderSound`), since the engine is asked about the sound and a
long recording's picture is most of its bytes.
"""

import math
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from otto.exceptions import NoSoundException
from otto.models import Clip, Edl
from otto.render import renderSound

# What a video's sound is written at for the engine: whisper's rate, which
# carries speech and the level of a mix; a transcription sends the same.
SOUND_RATE = 16000

_MEDIA = frozenset({'video', 'audio'})


def _round(value: float) -> float:
    """To the millisecond, a half up, as the lane's `round`."""
    return math.floor(value * 1000 + 0.5) / 1000


def _positive(value, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def clip_seconds(clip: Optional[dict]) -> float:
    """Seconds a clip occupies on the timeline."""
    if not clip:
        return 0.0
    try:
        seconds = float(clip.get('duration') or 0)
    except (TypeError, ValueError):
        return 0.0
    return seconds if math.isfinite(seconds) else 0.0


def in_of(clip: Optional[dict]) -> float:
    """Where in its source a clip starts playing, in seconds."""
    if not clip:
        return 0.0
    try:
        seconds = float(clip.get('inpoint') or 0)
    except (TypeError, ValueError):
        return 0.0
    return seconds if math.isfinite(seconds) else 0.0


def placed(clips: Optional[Iterable[Optional[dict]]]) -> List[dict]:
    """The clips end to end, as the editor lays them: each `{clip, index,
    start, length, inpoint}`, `start` on the timeline and `inpoint` in its
    source. A hole in the list is skipped."""
    start = 0.0
    out = []
    for index, clip in enumerate(clips or []):
        if clip is None:
            continue
        length = clip_seconds(clip)
        out.append(
            {
                'clip': clip,
                'index': index,
                'start': start,
                'length': length,
                'inpoint': in_of(clip),
            }
        )
        start += length
    return out


def sounding(clip: Optional[dict]) -> bool:
    """Whether a clip plays a file that can make a sound."""
    return bool(clip) and clip.get('type') in _MEDIA


def silences_on(at: dict, silences: Optional[Iterable[dict]]) -> List[dict]:
    """The file's silences (`[{start, end}]`, in its own seconds) that fall in
    a placed clip's window, in timeline seconds."""
    out = []
    for silence in silences or []:
        try:
            start = max(0.0, float(silence['start']) - at['inpoint'])
            end = min(at['length'], float(silence['end']) - at['inpoint'])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(start) and math.isfinite(end) and end - start > 0:
            out.append(
                {'start': _round(at['start'] + start), 'end': _round(at['start'] + end)}
            )
    return out


def timeline_end(at: Iterable[dict]) -> float:
    return max((a['start'] + a['length'] for a in at), default=0.0)


def levels(
    at: Sequence[dict], peaks_of: Callable[[str], Optional[dict]], rate=None
) -> dict:
    """The timeline's level over time, `{rate, values}`, each value 0 to 1 at
    `rate` a second: at each moment, the loudest value any clip sounding
    there plays from its file's `peaks` (`{rate, values}`, by `peaks_of` from
    the clip's name). `rate` is the files' highest when not given. Nothing
    sounding is 0."""
    placed_clips = [a for a in at if sounding(a['clip'])]
    files = {}
    for a in placed_clips:
        name = a['clip'].get('name')
        if name not in files:
            files[name] = peaks_of(name)
    rates = [_positive((p or {}).get('rate'), 0) for p in files.values()]
    chosen = _positive(rate, 0) or max((r for r in rates if r > 0), default=0)
    # To the timeline's end, a closing title included, so the levels and the
    # duration agree.
    duration = timeline_end(at)
    if not chosen or duration <= 0:
        return {'rate': chosen or 0, 'values': []}
    count = int(math.ceil(duration * chosen))
    values = [0.0] * count
    for a in placed_clips:
        peaks = files.get(a['clip'].get('name')) or {}
        file_rate = _positive(peaks.get('rate'), 0)
        file_values = peaks.get('values') or []
        if not file_rate or not file_values:
            continue
        first = int(math.floor(a['start'] * chosen))
        last = min(count, int(math.ceil((a['start'] + a['length']) * chosen)))
        for k in range(max(0, first), last):
            t = k / chosen - a['start']
            index = int(math.floor((a['inpoint'] + t) * file_rate))
            if 0 <= index < len(file_values):
                try:
                    level = float(file_values[index])
                except (TypeError, ValueError):
                    continue
                values[k] = max(values[k], min(1.0, max(0.0, level)))
    return {'rate': chosen, 'values': [_round(v) for v in values]}


def timeline_sound(clips: Iterable[Optional[dict]], analyses: Dict[str, dict]) -> dict:
    """The sound of a timeline from the engine's `analyses` of its files, by
    name, each with `peaks` and `silences`: `{duration, rate, levels,
    silences}`, every time in timeline seconds and the silences in order."""
    at = placed(clips)
    quiet = []
    for a in at:
        if not sounding(a['clip']):
            continue
        analysis = analyses.get(a['clip'].get('name')) or {}
        quiet.extend(silences_on(a, analysis.get('silences')))
    quiet.sort(key=lambda s: (s['start'], s['end']))
    level = levels(at, lambda name: (analyses.get(name) or {}).get('peaks'))
    return {
        'duration': _round(timeline_end(at)),
        'rate': level['rate'],
        'levels': level['values'],
        'silences': quiet,
    }


# --- a file's sound, for the engine -----------------------------------------------


class NoSoundTrack(ValueError):
    """The video has no sound where it plays. The message names the file."""


@contextmanager
def file_sound(
    path: str, kind: Optional[str], duration: Optional[float], rate=SOUND_RATE
):
    """The sound of the library file at `path`, as the engine is sent it:
    `(path, content type)`. An audio file goes as it is; a video's sound goes
    as a mono WAV at `rate`, written by otto into a directory of its own and
    removed afterwards. `duration` is the video's, from its probe; a video
    whose length is not known goes as it is. NoSoundTrack for a video with
    no sound."""
    if kind != 'video' or not duration or duration <= 0:
        yield path, None
        return
    folder = tempfile.mkdtemp(prefix='alfred-sound-')
    try:
        wav = os.path.join(folder, 'sound.wav')
        edl = Edl(clips=[Clip(type='video', name=path, duration=duration)])
        try:
            renderSound(edl, wav, rate=rate)
        except NoSoundException as exc:
            raise NoSoundTrack(f'{os.path.basename(path)} has no sound track') from exc
        yield wav, 'audio/wav'
    finally:
        shutil.rmtree(folder, ignore_errors=True)
