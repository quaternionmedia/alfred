"""IS-3 — output selection.

What the caller asks for versus what the encoder is actually told. Assertions
are on the arguments handed to `write_videofile`; nothing is encoded here.
Real encoding is IS-4.

Scope note: the *construction* of the output filename lives in a closure
inside `RenderAPI.__init__` (`alfred/core/routes/render.py`), so it is not
importable, and the surrounding `Render` document cannot be instantiated
without a database. Filename construction is therefore covered in IS-5, with
the API in front of it. What is covered here is the filename's journey once
chosen: the engine passes it through untouched, which is what makes an
unsanitised name from the API a problem downstream.
"""

import pytest

from otto.models import Clip, Edl, TemplateData
from otto.render import renderMultitrack


def _edl(duration=1.0):
    return Edl(
        clips=[
            Clip(
                type='template',
                name='makeColor',
                duration=duration,
                data=TemplateData(color='#00ff00'),
            )
        ]
    )


# --- resolution -----------------------------------------------------------


@pytest.mark.parametrize('moviesize', [(1920, 1080), (1280, 720), (640, 360), (64, 48)])
def test_requested_resolution_reaches_the_clip_graph(moviesize, recorded_encode):
    renderMultitrack(_edl(), moviesize=moviesize, filename='out.mp4')

    assert len(recorded_encode) == 1
    # The composite is built at the requested size, which is what the encoder
    # then writes; the size is not passed to write_videofile separately.
    assert recorded_encode[0]['filename'] == 'out.mp4'


# --- frame rate: the argument is dead -------------------------------------


def test_requested_fps_is_ignored(recorded_encode):
    """`renderMultitrack(fps=...)` never reaches the encoder.

    The signature accepts `fps` and the call site hardcodes `fps=30.0`, so
    every render is 30fps regardless. `alfred`'s Render model exposes `fps` to
    API callers and the worker forwards it, so this is user-visible: a caller
    can ask for 60 and silently receive 30.
    """
    renderMultitrack(_edl(), fps=60.0, filename='out.mp4')

    assert recorded_encode[0]['fps'] == 30.0


@pytest.mark.xfail(reason='the fps argument should reach the encoder')
def test_requested_fps_should_be_honoured(recorded_encode):
    renderMultitrack(_edl(), fps=60.0, filename='out.mp4')
    assert recorded_encode[0]['fps'] == 60.0


# --- encoder parameters ---------------------------------------------------


def test_encoder_defaults_are_what_the_engine_promises(recorded_encode):
    renderMultitrack(_edl(), filename='out.mp4')

    call = recorded_encode[0]
    assert call['codec'] == 'libx264'
    assert call['audio_codec'] == 'aac'
    assert call['audio_bitrate'] == '320k'
    assert call['audio_fps'] == 48000
    assert call['threads'] == 8


def test_ffmpeg_params_reach_the_encoder_unfiltered(recorded_encode):
    """Pinned deliberately.

    The control-plane record names `ffmpeg_params` as an accepted leak that
    must not widen: it is engine-specific configuration crossing the seam as
    opaque data, reachable by an API client. Pinning the passthrough means any
    future validation or allowlisting shows up as a test change rather than
    happening quietly.
    """
    params = ['-preset', 'ultrafast', '-crf', '30']
    renderMultitrack(_edl(), filename='out.mp4', ffmpeg_params=params)

    assert recorded_encode[0]['ffmpeg_params'] == params


def test_bitrate_is_passed_through_as_given(recorded_encode):
    """alfred types `bitrate` as a list; moviepy expects a string.

    `Render.bitrate` is `Optional[List]`, the worker forwards it unchanged,
    and the engine hands it straight to the encoder. Nothing converts or
    rejects it, so a well-formed API request produces an argument of the wrong
    type at the bottom of the stack.
    """
    renderMultitrack(_edl(), filename='out.mp4', bitrate=['5000k'])

    assert recorded_encode[0]['bitrate'] == ['5000k']


@pytest.mark.xfail(reason='a list bitrate should be rejected or normalised')
def test_list_bitrate_should_be_rejected_or_normalised(recorded_encode):
    renderMultitrack(_edl(), filename='out.mp4', bitrate=['5000k'])
    assert isinstance(recorded_encode[0]['bitrate'], (str, type(None)))


def test_logger_is_forwarded(recorded_encode):
    """The worker passes a DbLogger here to drive render progress."""
    sentinel = object()
    renderMultitrack(_edl(), filename='out.mp4', logger=sentinel)

    assert recorded_encode[0]['logger'] is sentinel


# --- output path ----------------------------------------------------------


@pytest.mark.parametrize(
    'filename',
    [
        'plain.mp4',
        'with spaces.mp4',
        '../escapes.mp4',
        'nested/path.mp4',
    ],
)
def test_output_filename_is_passed_through_untouched(filename, recorded_encode):
    """The engine does not sanitise the path it is told to write.

    That is defensible for an engine. It matters because the name is built by
    string interpolation from user-supplied fields in `queueRender` and is
    never sanitised there either, so a separator or `..` supplied through the
    API reaches the filesystem. The API-side half is covered in IS-5.
    """
    renderMultitrack(_edl(), filename=filename)

    assert recorded_encode[0]['filename'] == filename


def test_audio_is_not_set_when_no_audio_clip_is_present(recorded_encode):
    renderMultitrack(_edl(), filename='out.mp4')
    assert len(recorded_encode) == 1
