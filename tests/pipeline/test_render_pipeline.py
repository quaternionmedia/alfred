"""IS-4 — the rendering pipeline.

Clip-graph construction, plus one real encode proving the product's core
function works end to end.

The mocked group runs in the default tier. The real encode is marked
`needs_ffmpeg` and is kept deliberately tiny -- 320x240, two seconds -- so it
stays a second or two rather than a minute.
"""

import wave

import numpy as np
import pytest
from moviepy.video.VideoClip import VideoClip
from otto.exceptions import EmptyClipsException
from otto.models import Clip, Edl, TemplateData
from otto.render import AUDIO_FPS, generateEdl, renderMultitrack

SIZE = (64, 48)


def color_clip(duration=2.0, color='#00ff00', **overrides):
    attrs = dict(
        type='template',
        name='makeColor',
        duration=duration,
        data=TemplateData(color=color),
    )
    attrs.update(overrides)
    return Clip(**attrs)


# --- construction ---------------------------------------------------------


def test_an_empty_edl_is_refused():
    with pytest.raises(EmptyClipsException):
        generateEdl(Edl(clips=[]))


@pytest.mark.parametrize('count', [1, 2, 5])
def test_every_clip_becomes_a_layer(count):
    edl = Edl(clips=[color_clip() for _ in range(count)])

    video = generateEdl(edl, moviesize=SIZE)

    assert len(video.clips) == count


def test_layers_keep_edl_order():
    edl = Edl(
        clips=[
            color_clip(duration=1.0),
            color_clip(duration=2.0),
            color_clip(duration=3.0),
        ]
    )

    video = generateEdl(edl, moviesize=SIZE)

    assert [c.duration for c in video.clips] == [1.0, 2.0, 3.0]


def test_composite_is_built_at_the_requested_size():
    video = generateEdl(Edl(clips=[color_clip()]), moviesize=(320, 240))
    assert video.size == [320, 240] or tuple(video.size) == (320, 240)


# --- timing ---------------------------------------------------------------


def test_start_sets_the_layer_start():
    video = generateEdl(Edl(clips=[color_clip(start=3.0)]), moviesize=SIZE)
    assert video.clips[0].start == 3.0


def test_clips_are_layered_by_their_own_start_never_sequenced():
    """Contract C1: each clip is placed at its `start`, and none means 0.

    The editor sends every clip's start, so the engine must neither sequence
    clips itself nor treat `start: 0` differently from an absent start.
    """
    edl = Edl(
        clips=[
            color_clip(duration=2.0),
            color_clip(duration=2.0, start=0.0),
            color_clip(duration=1.0, start=2.0),
        ]
    )

    video = generateEdl(edl, moviesize=SIZE)

    assert [c.start for c in video.clips] == [0, 0, 2.0]
    assert video.duration == 3.0, 'the output ends with its last clip'


def test_positive_offset_also_sets_the_layer_start():
    """`offset` is documented as deprecated in favour of `start`."""
    video = generateEdl(Edl(clips=[color_clip(offset=2.0)]), moviesize=SIZE)
    assert video.clips[0].start == 2.0


def test_duration_sets_the_layer_duration():
    video = generateEdl(Edl(clips=[color_clip(duration=4.0)]), moviesize=SIZE)
    assert video.clips[0].duration == 4.0


def test_edl_duration_sets_the_composite_duration():
    edl = Edl(clips=[color_clip(duration=2.0)], duration=7.0)
    assert generateEdl(edl, moviesize=SIZE).duration == 7.0


def test_outpoint_trims_the_clip():
    """A clip plays its source from `inpoint` to `outpoint`.

    The line applying `outpoint` was commented out in the engine, so a clip
    trimmed in the editor rendered at its full `duration` -- a silent
    disagreement between the timeline and the video. With an outpoint,
    `duration` is not consulted; the editor keeps the two equal anyway.
    """
    edl = Edl(clips=[color_clip(duration=2.0, inpoint=1.0, outpoint=1.5)])
    assert generateEdl(edl, moviesize=SIZE).clips[0].duration == 0.5


# --- fades ----------------------------------------------------------------


@pytest.fixture
def recorded_fades(monkeypatch):
    calls = []

    def record(name, original):
        def wrapper(self, duration, *args, **kwargs):
            calls.append((name, duration))
            return original(self, duration, *args, **kwargs)

        return wrapper

    for name in ('crossfadein', 'crossfadeout'):
        monkeypatch.setattr(VideoClip, name, record(name, getattr(VideoClip, name)))
    return calls


# A clip's `fadeIn` and `fadeOut` are its only fades. Templates used to end in
# a one-second crossfade of their own, applied before the engine looked at the
# clip's fades -- so `fadeIn: 0` could not switch a template's fade off, and a
# requested fade stacked on top of the template's.


def test_a_requested_fade_is_the_only_fade(recorded_fades):
    generateEdl(Edl(clips=[color_clip(fadeIn=2.0, fadeOut=3.0)]), moviesize=SIZE)

    assert recorded_fades == [('crossfadein', 2.0), ('crossfadeout', 3.0)]


@pytest.mark.parametrize('off', [0, None])
def test_disabling_fades_leaves_a_template_clip_unfaded(recorded_fades, off):
    """0 or null is no fade at all, not a fade lasting no time."""
    generateEdl(Edl(clips=[color_clip(fadeIn=off, fadeOut=off)]), moviesize=SIZE)

    assert recorded_fades == []


# --- audio ----------------------------------------------------------------


def write_tone(path, seconds, frequency=440):
    """A mono sine as a WAV file, written without an encoder."""
    t = np.arange(int(seconds * AUDIO_FPS)) / AUDIO_FPS
    samples = (0.25 * np.sin(2 * np.pi * frequency * t) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(AUDIO_FPS)
        out.writeframes(samples.tobytes())
    return path


def loudness(track, start, end):
    """The peak amplitude of `track` between `start` and `end` seconds."""
    return float(np.abs(track.get_frame(np.arange(start, end, 1 / AUDIO_FPS))).max())


@pytest.mark.needs_ffmpeg
def test_an_audio_clip_is_mixed_into_the_sound_not_drawn(tmp_path):
    """An audio clip is heard from its `start`, and is never a picture layer.

    The engine built one and then fell through to the code for pictures, so a
    render with an audio clip crashed -- and alfred accepts them, named like
    any other media.
    """
    tone = write_tone(tmp_path / 'tone.wav', seconds=1.0)
    sound = Clip(
        type='audio', name=str(tone), duration=1.0, start=0.5, fadeIn=0, fadeOut=0
    )

    video = generateEdl(Edl(clips=[color_clip(duration=2.0), sound]), moviesize=SIZE)

    assert len(video.clips) == 1, 'the audio clip became a picture layer'
    assert loudness(video.audio, 0.0, 0.45) < 0.01, 'heard before its start'
    assert loudness(video.audio, 0.6, 1.4) > 0.05, 'not heard at all'


# --- the real thing -------------------------------------------------------


@pytest.mark.needs_ffmpeg
def test_a_two_clip_edl_renders_to_a_playable_file(tmp_path):
    """The one test that proves the product does what it exists to do.

    Nothing else in the suite encodes anything. Kept small on purpose.
    """
    from moviepy.video.io.VideoFileClip import VideoFileClip

    out = tmp_path / 'render.mp4'
    edl = Edl(
        clips=[
            color_clip(duration=1.0, color='#ff0000', fadeIn=0, fadeOut=0),
            color_clip(duration=1.0, color='#0000ff', start=1.0, fadeIn=0, fadeOut=0),
        ],
        duration=2.0,
    )

    renderMultitrack(
        edl,
        filename=str(out),
        moviesize=(320, 240),
        logger=None,
        ffmpeg_params=['-preset', 'ultrafast'],
    )

    assert out.exists(), 'no output file was written'
    assert out.stat().st_size > 0, 'output file is empty'

    with VideoFileClip(str(out)) as produced:
        assert tuple(produced.size) == (320, 240)
        assert produced.duration == pytest.approx(2.0, abs=0.2)
