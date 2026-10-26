"""A timeline's sound, transcribed into captions (contract K2).

The worker's half of `POST /project/{id}/captions/transcribe`. otto writes
what the project's saved timeline sounds like (`otto.render.renderSound`) --
its video and audio clips, timed exactly as a render times them -- as one
16 kHz mono WAV in a directory private to this job, removed afterwards. The
audio engine hears it (`utils.audio_engine`), and what it heard becomes
captions and the words kept for editing by text (`utils.captions`). The
file spans the whole timeline from 0, so the engine's times are already
timeline seconds.

alfred chose the codec, the channels and ffmpeg's options here, and had
moviepy write the file: media encoding in a control plane that is meant to do
none. It asks for a rate now, and says what a timeline with nothing to hear
means to the person waiting; the mix and the file are otto's.
"""

import os
import shutil
import tempfile
from typing import List, NamedTuple

from otto.exceptions import NoSoundException
from otto.models import Edl
from otto.render import SOUND_TYPES, renderSound

from ..models.captions import Caption, Word
from . import audio_engine
from .captions import captions_from_transcript, timeline_end, words_from_transcript
from .media import resolve_edl

# What a speech engine listens at: whisper resamples everything to it, so
# sending more is only a bigger upload.
SPEECH_RATE = 16000


class NothingToHear(ValueError):
    """The timeline makes no sound. Its message is for the person waiting."""


class Heard(NamedTuple):
    """What a transcription made of a timeline."""

    captions: List[Caption]
    # How many segments of speech the engine heard.
    segments: int
    # In timeline seconds (`words_from_transcript`).
    words: List[Word]


def sounding_clips(edl: Edl) -> list:
    """`edl`'s clips of a kind that can make a sound (otto's SOUND_TYPES:
    video and audio), in order; none when nothing in it could be heard.

    Asked before a transcription is queued, so that a timeline of templates
    and images is refused at once rather than by the worker. Whether the
    clips that can sound do -- a video may have no sound track -- only otto
    can say, from the files.
    """
    return [clip for clip in edl.clips if clip.type in SOUND_TYPES]


def mix_timeline(edl: Edl, path, rate=SPEECH_RATE) -> float:
    """Have otto write what `edl` sounds like to `path`: a `rate` Hz mono
    16-bit WAV, as long as the whole timeline (`otto.render.renderSound`).

    Media names must already be resolved (`utils.media.resolve_edl`).
    Returns the WAV's length in seconds; NothingToHear when there is none.
    """
    if not sounding_clips(edl):
        raise NothingToHear(
            'the timeline has no video or audio clips, so there is nothing to '
            'transcribe'
        )
    try:
        return renderSound(edl, path, rate=rate)
    except NoSoundException as exc:
        # Video clips, none of which has a sound track where it plays: otto
        # finds that out from the files.
        raise NothingToHear(
            "none of the timeline's clips has a sound track, so there is nothing "
            'to transcribe'
        ) from exc


def transcribe_timeline(edl_data: dict) -> Heard:
    """Captions for what the timeline `edl_data` says, how many segments of
    speech the engine heard, and the words it heard them in.

    Raises what stops it, with a message for the person waiting: a media name
    the library does not hold (MediaNameError), a clip otto cannot play
    (otto's EdlException, naming the clip by its place in the timeline), a
    timeline with nothing to hear, or in which no speech was heard
    (NothingToHear), an engine that is missing, refuses the sound or fails
    (AudioEngineError), or more captions or words than a project carries
    (TooManyCaptions, TooManyWords).
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
    words = words_from_transcript(transcript.segments, until=until)
    return Heard(captions, len(transcript.segments), words)
