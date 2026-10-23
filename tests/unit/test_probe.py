"""M2 -- how long a media file runs, and how big its picture is.

The editor added every library clip as five seconds long, because nothing
would say how long a file was. The engine says (`otto.media.probe`), and
`utils.probe` remembers its answer until the file changes.

How ffmpeg's description is read, and what each kind of clip leaves out, is
otto's and is tested there, against ffmpeg's own output. Here: that alfred
asks once per version of a file, keeps a bounded number of answers, turns a
failure into nothing known, and asks again after a timeout -- and, on real
files, that what comes back is what the library lists.
"""

import os
import subprocess

import pytest
from otto.media import UNKNOWN, MediaInfo

from alfred.core.utils import probe as probing

CLIP = MediaInfo(duration=3.02, width=320, height=180, fps=24.0, sound=True)


class Stat:
    def __init__(self, mtime_ns=1, size=10):
        self.st_mtime_ns, self.st_size = mtime_ns, size


@pytest.fixture
def described(monkeypatch):
    """Record each time the engine would be asked, and answer for a clip."""
    calls = []

    def probe_file(path, kind=None):
        calls.append(path)
        return CLIP

    monkeypatch.setattr(probing, 'probe_file', probe_file)
    monkeypatch.setattr(probing, '_cache', probing.ProbeCache(size=3))
    return calls


class TestTheCache:
    def test_an_unchanged_file_is_probed_once(self, described):
        first = probing.probe('/v/a.mp4', 'video', Stat())
        again = probing.probe('/v/a.mp4', 'video', Stat())
        assert first == again == CLIP and described == ['/v/a.mp4']

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

    def test_the_kind_is_handed_to_the_engine(self, monkeypatch):
        asked = []
        monkeypatch.setattr(
            probing, 'probe_file', lambda path, kind=None: asked.append(kind) or CLIP
        )
        monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
        probing.probe('/v/a.png', 'image', Stat())
        assert asked == ['image']


class TestWhenTheEngineFails:
    def test_a_failure_is_unknown_and_remembered(self, monkeypatch):
        calls = []

        def broken(path, kind=None):
            calls.append(path)
            raise OSError('no ffmpeg')

        monkeypatch.setattr(probing, 'probe_file', broken)
        monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert len(calls) == 1

    def test_a_timeout_is_unknown_and_tried_again(self, monkeypatch):
        calls = []

        def slow(path, kind=None):
            calls.append(path)
            raise TimeoutError(f'ffmpeg took longer than 10s to describe {path}')

        monkeypatch.setattr(probing, 'probe_file', slow)
        monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert probing.probe('/v/a.mp4', 'video', Stat()) == UNKNOWN
        assert len(calls) == 2


def make_media(path, *args):
    """Write `path` with the ffmpeg the engine uses. Test fixtures only:
    alfred itself runs no ffmpeg."""
    import imageio_ffmpeg

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-nostdin',
            '-y',
            '-loglevel',
            'error',
            *args,
            str(path),
        ],
        check=True,
    )


@pytest.fixture
def fresh_cache(monkeypatch):
    monkeypatch.setattr(probing, '_cache', probing.ProbeCache())


@pytest.mark.needs_ffmpeg
class TestARealProbe:
    """The engine, on files the bundled ffmpeg just made."""

    def test_a_video(self, tmp_path, fresh_cache):
        path = tmp_path / 'bars.mp4'
        make_media(
            path,
            *('-f', 'lavfi', '-i', 'smptebars=size=320x180:rate=24:duration=2'),
            *('-pix_fmt', 'yuv420p'),
        )
        found = probing.probe(path, 'video', os.stat(path))
        assert (found.width, found.height, found.fps) == (320, 180, 24.0)
        assert found.duration == pytest.approx(2.0, abs=0.1)

    def test_an_image(self, tmp_path, fresh_cache):
        path = tmp_path / 'still.png'
        make_media(
            path, '-f', 'lavfi', '-i', 'color=c=red:size=40x30', '-frames:v', '1'
        )
        assert probing.probe(path, 'image', os.stat(path)) == MediaInfo(
            width=40, height=30
        )

    def test_a_sound(self, tmp_path, fresh_cache):
        path = tmp_path / 'tone.mp3'
        make_media(path, '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.5')
        found = probing.probe(path, 'audio', os.stat(path))
        assert found.duration == pytest.approx(1.5, abs=0.1)
        assert found.width is None and found.fps is None

    def test_a_name_ffmpeg_might_read_as_a_protocol(self, tmp_path, fresh_cache):
        """`file:` in front, so a file called `concat:...` is just a file."""
        path = tmp_path / 'concat:x.mp4'
        try:
            path.write_bytes(b'not a video')
        except OSError:
            pytest.skip('this filesystem does not allow : in a name')
        assert probing.probe(path, 'video', os.stat(path)) == UNKNOWN
