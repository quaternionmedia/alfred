"""M2 -- how long a media file runs, and how big its picture is.

The editor added every library clip as five seconds long, because nothing
would say how long a file was. `utils.probe` reads ffmpeg's description of the
input -- no decoding -- and remembers it until the file changes.

The parser is pinned against what ffmpeg actually prints: the samples in
`ffmpeg_samples.py` are its output, from the 4.2 build imageio-ffmpeg ships
and from a current build (stream ids in brackets, rotation as side data).
"""

import os
import subprocess

import pytest

from alfred.core.utils import probe as probing
from alfred.core.utils.probe import UNKNOWN, Probe, parse
from tests.unit.ffmpeg_samples import (
    GIF,
    MP3,
    MP3_WITH_COVER_ART,
    MP4_WITH_SOUND,
    PNG,
    ROTATED_42,
    ROTATED_CURRENT,
    WEBM_NTSC,
)


class TestParsing:
    def test_a_video_with_sound(self):
        assert parse(MP4_WITH_SOUND, 'video') == Probe(
            duration=3.02, width=320, height=180, fps=24.0
        )

    def test_a_fractional_frame_rate(self):
        assert parse(WEBM_NTSC, 'video') == Probe(
            duration=2.0, width=64, height=48, fps=29.97
        )

    def test_the_codec_tag_is_not_taken_for_a_size(self):
        """`(avc1 / 0x31637661)` has digits either side of an x."""
        assert parse(MP4_WITH_SOUND, 'video').width == 320

    def test_audio_has_a_duration_and_no_picture(self):
        assert parse(MP3, 'audio') == Probe(duration=1.54)

    def test_cover_art_is_not_audio_s_picture(self):
        assert parse(MP3_WITH_COVER_ART, 'audio') == Probe(duration=1.54)

    def test_an_image_has_a_size_and_nothing_else(self):
        """ffmpeg gives a still a nominal 25 tbr; that is not a frame rate."""
        assert parse(PNG, 'image') == Probe(width=40, height=30)

    def test_an_animated_gif_is_still_an_image(self):
        """An image clip shows it still; how long it runs is the clip's."""
        assert parse(GIF, 'image') == Probe(width=80, height=60)

    @pytest.mark.parametrize('description', [ROTATED_42, ROTATED_CURRENT])
    def test_a_quarter_turn_swaps_the_picture_s_sides(self, description):
        """What is shown, which is what the editor lays out."""
        found = parse(description, 'video')
        assert found.height > found.width

    def test_a_current_ffmpeg_s_output(self):
        assert parse(ROTATED_CURRENT, 'video') == Probe(
            duration=62.5, width=1080, height=1920, fps=59.94
        )

    def test_nothing_recognisable_is_unknown(self):
        assert parse('file: Invalid data found when processing input', 'video') == (
            UNKNOWN
        )


class Stat:
    def __init__(self, mtime_ns=1, size=10):
        self.st_mtime_ns, self.st_size = mtime_ns, size


@pytest.fixture
def described(monkeypatch):
    """Record each time ffmpeg would be asked, and answer with a sample."""
    calls = []

    def describe(path):
        calls.append(path)
        return MP4_WITH_SOUND

    monkeypatch.setattr(probing, 'describe', describe)
    monkeypatch.setattr(probing, '_cache', probing.ProbeCache(size=3))
    return calls


class TestTheCache:
    def test_an_unchanged_file_is_probed_once(self, described):
        first = probing.probe('/v/a.mp4', 'video', Stat())
        again = probing.probe('/v/a.mp4', 'video', Stat())
        assert first == again and described == ['/v/a.mp4']

    def test_a_modified_file_is_probed_again(self, described):
        probing.probe('/v/a.mp4', 'video', Stat(mtime_ns=1))
        probing.probe('/v/a.mp4', 'video', Stat(mtime_ns=2))
        assert len(described) == 2

    def test_a_file_of_another_size_is_probed_again(self, described):
        probing.probe('/v/a.mp4', 'video', Stat(size=10))
        probing.probe('/v/a.mp4', 'video', Stat(size=11))
        assert len(described) == 2

    def test_it_is_bounded(self, described):
        for name in 'abcde':
            probing.probe(f'/v/{name}.mp4', 'video', Stat())
        assert len(probing._cache) == 3
        probing.probe('/v/a.mp4', 'video', Stat())
        assert described.count('/v/a.mp4') == 2, 'the oldest entry was not evicted'

    def test_the_most_recently_used_is_kept(self, described):
        for name in 'abc':
            probing.probe(f'/v/{name}.mp4', 'video', Stat())
        probing.probe('/v/a.mp4', 'video', Stat())  # a is now the newest
        probing.probe('/v/d.mp4', 'video', Stat())  # evicts b, not a
        probing.probe('/v/a.mp4', 'video', Stat())
        assert described.count('/v/a.mp4') == 1


class TestWhenFfmpegFails:
    def test_a_failure_is_unknown_and_remembered(self, monkeypatch):
        calls = []

        def broken(path):
            calls.append(path)
            raise OSError('no ffmpeg')

        monkeypatch.setattr(probing, 'describe', broken)
        monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert len(calls) == 1

    def test_a_timeout_is_unknown_and_tried_again(self, monkeypatch):
        calls = []

        def slow(path):
            calls.append(path)
            raise subprocess.TimeoutExpired('ffmpeg', probing.PROBE_TIMEOUT)

        monkeypatch.setattr(probing, 'describe', slow)
        monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert len(calls) == 2


def make_media(path, *args):
    subprocess.run(
        [
            probing.ffmpeg_binary(),
            '-nostdin',
            '-y',
            '-loglevel',
            'error',
            *args,
            str(path),
        ],
        check=True,
    )


@pytest.mark.needs_ffmpeg
class TestARealProbe:
    """The bundled ffmpeg, on files it just made."""

    def test_a_video(self, tmp_path):
        path = tmp_path / 'bars.mp4'
        make_media(
            path,
            *('-f', 'lavfi', '-i', 'smptebars=size=320x180:rate=24:duration=2'),
            *('-pix_fmt', 'yuv420p'),
        )
        found = probing.probe(path, 'video', os.stat(path))
        assert (found.width, found.height, found.fps) == (320, 180, 24.0)
        assert found.duration == pytest.approx(2.0, abs=0.1)

    def test_an_image(self, tmp_path):
        path = tmp_path / 'still.png'
        make_media(
            path, '-f', 'lavfi', '-i', 'color=c=red:size=40x30', '-frames:v', '1'
        )
        assert probing.probe(path, 'image', os.stat(path)) == Probe(width=40, height=30)

    def test_a_sound(self, tmp_path):
        path = tmp_path / 'tone.mp3'
        make_media(path, '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.5')
        found = probing.probe(path, 'audio', os.stat(path))
        assert found.duration == pytest.approx(1.5, abs=0.1)
        assert found.width is None and found.fps is None

    def test_a_name_ffmpeg_might_read_as_a_protocol(self, tmp_path):
        """`file:` in front, so a file called `concat:...` is just a file."""
        path = tmp_path / 'concat:x.mp4'
        try:
            path.write_bytes(b'not a video')
        except OSError:
            pytest.skip('this filesystem does not allow : in a name')
        assert probing.probe(path, 'video', os.stat(path)) == UNKNOWN
