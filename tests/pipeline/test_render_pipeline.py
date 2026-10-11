"""IS-4 — the rendering pipeline.

Clip-graph construction, plus one real encode proving the product's core
function works end to end.

The mocked group runs in the default tier. The real encode is marked
`needs_ffmpeg` and is kept deliberately tiny -- 320x240, two seconds -- so it
stays a second or two rather than a minute.
"""

import pytest

from moviepy.video.VideoClip import VideoClip

from otto.exceptions import EmptyClipsException
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl, renderMultitrack

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


def test_outpoint_is_ignored():
    """`outpoint` is accepted by the model and never applied.

    The line that would trim to it is commented out in `otto/render.py`, so a
    clip trimmed in the editor renders at its full `duration`. The editor
    maintains `inpoint`/`outpoint` as the user drags, which makes this a
    silent disagreement between what the timeline shows and what is rendered.
    """
    edl = Edl(clips=[color_clip(duration=2.0, inpoint=1.0, outpoint=1.5)])

    video = generateEdl(edl, moviesize=SIZE)

    assert video.clips[0].duration == 2.0


@pytest.mark.xfail(reason='outpoint should trim the clip')
def test_outpoint_should_trim_the_clip():
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


# The `makeColor` template hardcodes `.crossfadein(1).crossfadeout(1)` on
# every clip it builds, before `generateEdl` looks at the clip's own fadeIn
# and fadeOut. So the recorded calls are the template's pair plus, when the
# clip asks for fades, the engine's pair on top.
TEMPLATE_FADES = [('crossfadein', 1), ('crossfadeout', 1)]


def test_the_engine_applies_the_requested_fade_durations(recorded_fades):
    generateEdl(Edl(clips=[color_clip(fadeIn=2.0, fadeOut=3.0)]), moviesize=SIZE)

    assert ('crossfadein', 2.0) in recorded_fades
    assert ('crossfadeout', 3.0) in recorded_fades


def test_zero_skips_the_engine_fade(recorded_fades):
    """The guard is truthiness, so 0 skips rather than fading for 0 seconds."""
    generateEdl(Edl(clips=[color_clip(fadeIn=0, fadeOut=0)]), moviesize=SIZE)

    assert not [d for _, d in recorded_fades if d == 0]


def test_a_template_clip_is_faded_even_when_fades_are_disabled(
    recorded_fades,
):
    """`fadeIn=0` does not produce an unfaded template clip.

    The template applied its own one-second crossfade before the engine ever
    consulted the clip's fade settings, so the only thing switching fades off
    achieves is removing the *second* fade.
    """
    generateEdl(Edl(clips=[color_clip(fadeIn=0, fadeOut=0)]), moviesize=SIZE)

    assert recorded_fades == TEMPLATE_FADES


@pytest.mark.xfail(reason='fadeIn=0 should render a template clip unfaded')
def test_disabling_fades_should_leave_a_template_clip_unfaded(recorded_fades):
    generateEdl(Edl(clips=[color_clip(fadeIn=0, fadeOut=0)]), moviesize=SIZE)
    assert recorded_fades == []


def test_a_template_clip_asking_for_fades_gets_two(recorded_fades):
    """Requesting a fade stacks the engine's on top of the template's.

    A caller asking for a two-second fade in gets the template's one-second
    crossfade *and* a two-second one, which is not what either the model or
    the editor implies.
    """
    generateEdl(Edl(clips=[color_clip(fadeIn=2.0, fadeOut=3.0)]), moviesize=SIZE)

    assert len([c for c in recorded_fades if c[0] == 'crossfadein']) == 2
    assert len([c for c in recorded_fades if c[0] == 'crossfadeout']) == 2


@pytest.mark.xfail(reason='a requested fade should replace the template fade')
def test_a_requested_fade_should_not_stack_on_the_template_fade(
    recorded_fades,
):
    generateEdl(Edl(clips=[color_clip(fadeIn=2.0)]), moviesize=SIZE)
    assert len([c for c in recorded_fades if c[0] == 'crossfadein']) == 1


# --- audio ----------------------------------------------------------------


def test_an_audio_clip_is_also_appended_as_a_video_layer():
    """Pinned as suspect rather than asserted as correct.

    The `audio` branch sets the composite's audio track *and* falls through to
    `clips.append(c)`, so an audio clip becomes a layer in the video composite
    as well. Flagged for review; not changed here.
    """
    import inspect
    from otto import render

    source = inspect.getsource(render.generateEdl)
    audio_branch = source.split("elif clip.type == 'audio':")[1]
    before_next_branch = audio_branch.split('elif')[0]

    assert (
        'clips.append' not in before_next_branch
    ), 'if the audio branch gains its own append/continue, revisit this test'


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
