"""K2, for real: captions drawn into an encoded video, and a timeline heard.

Two halves of the captions pipeline that nothing else runs:

- **Drawing.** A timeline with captions is encoded, as the worker would from
  a render's payload, and frames are read back from the file: the caption box
  is on screen while a caption is shown -- text brighter than the picture, a
  translucent box darker than it -- and gone when none is, in the band the
  style's position names.
- **Hearing.** A timeline whose audio and video clips sound at known moments
  is mixed by otto into a 16 kHz mono WAV, and the stub engine
  (`tests/stubs/audio_engine.py`), standing in for vox's media client and an
  engine behind it, hears where the sound is -- so the captions that come
  back are timed by the timeline, not by the files.
"""

import os
import subprocess
import tempfile
import types
import wave

import numpy as np
import pytest
from otto.models import Edl
from otto.render import renderMultitrack

from alfred import config
from alfred.core.models.captions import Caption, CaptionStyle
from alfred.core.utils import audio_engine
from alfred.core.utils.captions import timeline_end, with_captions
from alfred.core.utils.transcription import mix_timeline, transcribe_timeline
from tests.stubs import audio_engine as stub

SIZE = (640, 360)
BACKGROUND = (32, 48, 64)


def background(duration):
    return {
        'type': 'template',
        'name': 'makeColor',
        'duration': duration,
        'start': 0,
        'fadeIn': 0,
        'fadeOut': 0,
        'data': {'color': '#203040'},
    }


def render(tmp_path, edl, size=SIZE):
    out = tmp_path / 'captioned.mp4'
    renderMultitrack(
        Edl.parse_obj(edl),
        filename=str(out),
        moviesize=size,
        fps=10,
        logger=None,
        ffmpeg_params=['-preset', 'ultrafast', '-crf', '18'],
    )
    return out


def frames_at(path, times):
    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(str(path)) as video:
        return {t: video.get_frame(t).astype(int) for t in times}


def band(frame, top, bottom):
    """Rows `top` to `bottom` as shares of the height."""
    height = frame.shape[0]
    return frame[int(top * height) : int(bottom * height)]


def bright(region):
    """Pixels of text: brighter than the picture in every channel."""
    return int((region.min(axis=2) > 170).sum())


def shaded(region):
    """Pixels of the box: darker than the picture in every channel."""
    return int((region < np.array(BACKGROUND) - 10).all(axis=2).sum())


@pytest.mark.needs_ffmpeg
@pytest.mark.needs_imagemagick
def test_a_caption_is_on_screen_while_it_is_shown_and_only_then(tmp_path):
    captions = [
        Caption(start=0.5, end=1.2, text='The first thing said'),
        Caption(start=1.8, end=2.5, text='Then the second'),
    ]
    timeline = {'clips': [background(3.0)], 'duration': 3.0}
    edl = with_captions(
        timeline,
        captions,
        CaptionStyle(),
        SIZE,
        until=timeline_end(Edl.parse_obj(timeline)),
    )
    frames = frames_at(render(tmp_path, edl), [0.2, 0.8, 1.5, 2.2, 2.8])

    for t, frame in frames.items():
        bottom = band(frame, 0.75, 0.96)
        shown = 0.5 <= t < 1.2 or 1.8 <= t < 2.5
        if shown:
            assert bright(bottom) > 40, f'no caption text at {t}s'
            assert shaded(bottom) > 400, f'no box behind the caption at {t}s'
        else:
            assert bright(bottom) == 0, f'a caption at {t}s, when none is shown'
            assert shaded(bottom) < 20, f'a box at {t}s, when none is shown'
        # Never above the bottom band: nothing drawn mid-frame.
        assert bright(band(frame, 0.2, 0.7)) == 0


@pytest.mark.needs_ffmpeg
@pytest.mark.needs_imagemagick
def test_the_style_moves_and_colours_it(tmp_path):
    captions = [Caption(start=0.0, end=1.0, text='Up here, and yellow')]
    style = CaptionStyle(position='top', color='#ffff00', bg='')
    edl = with_captions({'clips': [background(1.0)]}, captions, style, SIZE)
    frame = frames_at(render(tmp_path, edl), [0.5])[0.5]

    top, bottom = band(frame, 0.04, 0.25), band(frame, 0.75, 0.96)
    yellow = ((top[..., 0] > 170) & (top[..., 1] > 170) & (top[..., 2] < 120)).sum()
    assert yellow > 40, 'no yellow text at the top'
    assert shaded(top) < 20, 'a box drawn though the style asked for none'
    assert bright(bottom) == 0


@pytest.mark.needs_ffmpeg
@pytest.mark.needs_imagemagick
def test_a_long_caption_wraps_inside_the_frame(tmp_path):
    text = (
        'A caption long enough that it cannot possibly fit on one line of a small frame'
    )
    edl = with_captions(
        {'clips': [background(1.0)]},
        [Caption(start=0, end=1, text=text)],
        None,
        (320, 180),
    )
    frame = frames_at(render(tmp_path, edl, size=(320, 180)), [0.5])[0.5]
    rows = np.flatnonzero((frame.min(axis=2) > 170).any(axis=1))
    columns = (frame.min(axis=2) > 170).any(axis=0)
    # More than one line of 12-pixel text, and none of it at the very edges.
    assert rows.size and rows[-1] - rows[0] > 20
    assert not columns[:4].any() and not columns[-4:].any()


# --- hearing a timeline -----------------------------------------------------


def write_bursts(path, rate=44100):
    """The stub's fixture: two bursts of tone, at 0.5-1.5 s and 2.0-3.2 s."""
    stub.write_fixture(str(path.parent))
    os.replace(path.parent / stub.FIXTURE, path)
    return path


def write_talking_video(path):
    """A 2 s video whose sound is a 1 s tone, then silence."""
    import imageio_ffmpeg

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-nostdin',
            '-v',
            'error',
            '-y',
            '-f',
            'lavfi',
            '-i',
            'testsrc=size=64x36:rate=10:duration=2',
            '-f',
            'lavfi',
            '-i',
            'sine=frequency=550:duration=1',
            '-af',
            'apad',
            '-t',
            '2',
            '-pix_fmt',
            'yuv420p',
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    write_bursts(tmp_path / 'speech.wav')
    write_talking_video(tmp_path / 'talking.mp4')
    return tmp_path


TIMELINE = {
    'clips': [
        background(7.0),
        # The fixture's bursts, 1.0 s later on the timeline: 1.5-2.5, 3.0-4.2.
        {
            'type': 'audio',
            'name': 'videos/speech.wav',
            'start': 1.0,
            'duration': 4.0,
            'fadeIn': 0,
            'fadeOut': 0,
        },
        # The video's tone, from 5.0 to 6.0.
        {
            'type': 'video',
            'name': 'videos/talking.mp4',
            'start': 5.0,
            'duration': 2.0,
            'fadeIn': 0,
            'fadeOut': 0,
        },
    ]
}


@pytest.mark.needs_ffmpeg
def test_the_timeline_is_mixed_to_16khz_mono_where_it_sounds(library, tmp_path):
    from alfred.core.utils.media import resolve_edl

    out = tmp_path / 'mix.wav'
    length = mix_timeline(resolve_edl(Edl.parse_obj(TIMELINE)), out)

    with wave.open(str(out)) as reader:
        assert (
            reader.getframerate(),
            reader.getnchannels(),
            reader.getsampwidth(),
        ) == (
            16000,
            1,
            2,
        )
        frames = reader.getnframes()
        samples = np.frombuffer(reader.readframes(frames), dtype='<i2')
    assert length == pytest.approx(7.0, abs=0.05)
    assert frames / 16000 == pytest.approx(7.0, abs=0.05)

    heard = stub.stretches(stub.array('h', samples.tobytes()))
    assert [(round(a, 1), round(b, 1)) for a, b in heard] == [
        (1.5, 2.5),
        (3.0, 4.2),
        (5.0, 6.0),
    ]


@pytest.mark.needs_ffmpeg
def test_the_mix_lasts_until_the_timeline_ends_where_a_template_ends_it(
    library, tmp_path
):
    """Captions are clamped to the timeline's end and timed from its start,
    so the WAV must run that long even when what ends it makes no sound."""
    from alfred.core.utils.media import resolve_edl

    out = tmp_path / 'mix.wav'
    timeline = {'clips': [background(8.0), TIMELINE['clips'][1]]}
    edl = resolve_edl(Edl.parse_obj(timeline))

    length = mix_timeline(edl, out)

    with wave.open(str(out)) as reader:
        frames = reader.getnframes()
    assert timeline_end(edl) == 8.0
    assert length == pytest.approx(8.0, abs=0.05)
    assert frames / 16000 == pytest.approx(8.0, abs=0.05)


@pytest.mark.needs_ffmpeg
def test_a_timeline_with_nothing_to_hear_says_so(library, tmp_path):
    from alfred.core.utils.transcription import NothingToHear

    with pytest.raises(NothingToHear):
        mix_timeline(Edl.parse_obj({'clips': [background(1.0)]}), tmp_path / 'x.wav')


@pytest.mark.needs_ffmpeg
def test_a_timeline_whose_video_has_no_sound_track_says_so(library, tmp_path):
    """Only the file can say a video is silent: otto opens it, finds no sound,
    and alfred says so in the words the browser suite reads."""
    import imageio_ffmpeg

    from alfred.core.utils.media import resolve_edl
    from alfred.core.utils.transcription import NothingToHear

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-nostdin',
            '-v',
            'error',
            '-y',
            '-f',
            'lavfi',
            '-i',
            'testsrc=size=64x36:rate=10:duration=2',
            '-pix_fmt',
            'yuv420p',
            str(library / 'silent.mp4'),
        ],
        check=True,
    )
    out = tmp_path / 'x.wav'
    timeline = {
        'clips': [
            background(2.0),
            {'type': 'video', 'name': 'videos/silent.mp4', 'duration': 2.0},
        ]
    }

    with pytest.raises(NothingToHear, match='has a sound track'):
        mix_timeline(resolve_edl(Edl.parse_obj(timeline)), out)
    assert not out.exists()


class StubMediaEngine:
    """Stands in for vox's media client, driving the stub engine in-process:
    the same requests vox would make, against the same answers."""

    def __init__(self, contract, base_url, timeout):
        from fastapi.testclient import TestClient

        self.client = TestClient(stub.app)

    def upload(self, path, content_type):
        with open(path, 'rb') as handle:
            res = self.client.post(
                '/api/media',
                content=handle.read(),
                headers={'content-type': content_type},
            )
        assert res.status_code == 201, res.text
        return res.json()['media_id']

    def transcribe(self, handle, language=None, words=True):
        res = self.client.post(
            f'/api/media/{handle}/transcribe', params={'words': words}
        )
        assert res.status_code == 200, res.text
        return res.json()

    def close(self, handle):
        self.client.delete(f'/api/media/{handle}')


@pytest.mark.needs_ffmpeg
def test_a_timeline_is_heard_into_captions_on_its_own_clock(library, monkeypatch):
    fake = types.SimpleNamespace(MediaEngine=StubMediaEngine)
    monkeypatch.setattr(audio_engine, '_vox_media', lambda: fake)
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://stub.test')
    stub.uploads.clear()
    stub.media.clear()
    before = set(os.listdir(tempfile.gettempdir()))

    captions, segments = transcribe_timeline(TIMELINE)

    assert segments == 3
    assert [c.text for c in captions] == list(stub.SCRIPT)
    assert [(round(c.start, 1), round(c.end, 1)) for c in captions] == [
        (1.5, 2.5),
        (3.0, 4.2),
        (5.0, 6.0),
    ]
    # What was sent: the mix, as speech engines want it.
    [sent] = stub.uploads
    assert (sent['content_type'], sent['sample_rate'], sent['channels']) == (
        'audio/wav',
        16000,
        1,
    )
    assert sent['duration'] == pytest.approx(7.0, abs=0.05)
    # And nothing of it is left behind.
    left = {
        name
        for name in set(os.listdir(tempfile.gettempdir())) - before
        if name.startswith('alfred-transcribe-')
    }
    assert not left
    assert stub.media == {}, 'the upload was not dropped from the engine'
