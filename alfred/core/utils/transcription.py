"""A timeline's sound, transcribed into captions (contract K2).

The worker's half of `POST /project/{id}/captions/transcribe`. otto builds the
project's saved timeline -- the clips that can make a sound, timed exactly as
a render times them -- and writes what it would play as one 16 kHz mono WAV
in a directory private to this job, removed afterwards. The audio engine
hears it (`utils.audio_engine`), and what it heard becomes captions
(`utils.captions`). The file spans the whole timeline from 0, so the engine's
times are already timeline seconds.
"""

import os
import shutil
import tempfile

from otto.models import Edl

from . import audio_engine
from .captions import captions_from_transcript, timeline_end
from .media import resolve_edl

# What a speech engine listens at: whisper resamples everything to it, so
# sending more is only a bigger upload.
SPEECH_RATE = 16000

# What the timeline is mixed at, as a render mixes it (otto's AUDIO_FPS);
# ffmpeg resamples to SPEECH_RATE as it writes, rather than the mix picking
# the nearest sample.
MIX_RATE = 48000

# The clips that can make a sound. A template or an image is silent, and
# building one costs an ImageMagick run for nothing.
SOUNDING = frozenset({'video', 'audio'})

# The picture is never looked at; a video is decoded at the smallest size
# that is still a frame.
PICTURE = (64, 36)


class NothingToHear(ValueError):
    """The timeline makes no sound. Its message is for the person waiting."""


def sounding_timeline(edl: Edl):
    """`edl`'s clips that can make a sound, as long as the whole timeline --
    so silence stands where the rest were and times do not move -- or None
    when none can."""
    clips = [clip for clip in edl.clips if clip.type in SOUNDING]
    if not clips:
        return None
    return Edl(clips=clips, duration=timeline_end(edl))


def mix_timeline(edl: Edl, path, rate=SPEECH_RATE) -> float:
    """Write what `edl` sounds like to `path`, a `rate` Hz mono 16-bit WAV.

    Media names must already be resolved (`utils.media.resolve_edl`).
    Returns the sound's length in seconds; NothingToHear when there is none.
    """
    from otto.render import generateEdl

    sounding = sounding_timeline(edl)
    if sounding is None:
        raise NothingToHear(
            'the timeline has no video or audio clips, so there is nothing to '
            'transcribe'
        )
    video = generateEdl(sounding, moviesize=PICTURE)
    sound = video.audio
    if sound is None:
        raise NothingToHear(
            "none of the timeline's clips has a sound track, so there is nothing "
            'to transcribe'
        )
    try:
        sound.write_audiofile(
            str(path),
            fps=MIX_RATE,
            nbytes=2,
            codec='pcm_s16le',
            # Output options, after moviepy's own: one channel, resampled by
            # ffmpeg. The last -ar given is the one ffmpeg uses.
            ffmpeg_params=['-ac', '1', '-ar', str(rate)],
            logger=None,
        )
        return float(sound.duration)
    finally:
        try:
            video.close()
        except Exception:  # noqa: BLE001 - closing is housekeeping
            pass


def transcribe_timeline(edl_data: dict):
    """Captions for what the timeline `edl_data` says, and how many segments
    of speech the engine heard.

    Raises what stops it, with a message for the person waiting: a media name
    the library does not hold (MediaNameError), a timeline with nothing to
    hear, or in which no speech was heard (NothingToHear), an engine that is
    missing, refuses the sound or fails (AudioEngineError), or more captions
    than a project carries (TooManyCaptions).
    """
    edl = resolve_edl(Edl.parse_obj(edl_data))
    until = timeline_end(edl)
    folder = tempfile.mkdtemp(prefix='alfred-transcribe-')
    try:
        path = os.path.join(folder, 'timeline.wav')
        mix_timeline(edl, path)
        transcript = audio_engine.transcribe(path, 'audio/wav')
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    captions = captions_from_transcript(transcript.segments, until=until)
    if not captions:
        # Music, silence, or nothing the engine could make out. Said as a
        # failure, so the captions the project has are not replaced by none.
        raise NothingToHear("the audio engine heard no speech in the timeline's sound")
    return captions, len(transcript.segments)
