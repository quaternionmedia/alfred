"""How long a media file runs, and how big its picture is (contract M2).

The editor added every library clip to the timeline as five seconds long,
because nothing on the server would say how long a file was. This asks ffmpeg
-- the same binary the engine encodes with, from imageio-ffmpeg -- and keeps
the answer, so a listing does not start a process per file every time.

`ffmpeg -i <file>` describes the input on stderr and exits, without decoding
anything; that description is all a probe reads. Results are cached by the
file's path, modification time and size, so an edited or replaced file is
probed again and an unchanged one never is. The cache is bounded.
"""

import re
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from os import stat_result
from threading import Lock
from typing import Optional

# Long enough for a large file on a slow disk; ffmpeg reads only the headers.
PROBE_TIMEOUT = 10

# Entries kept, most recently used first out last. A library listing touches
# every file, so this bounds memory for libraries larger than it, at the cost
# of probing them again.
CACHE_SIZE = 2048


@dataclass(frozen=True)
class Probe:
    """What is known about a media file. Anything unknown is None."""

    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None


UNKNOWN = Probe()

_DURATION = re.compile(r'Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)')
_VIDEO_STREAM = re.compile(r'Stream #\d+:\d+.*?: Video: (?P<description>.*)')
# The frame size follows ", " in the stream line. Codec tags such as
# `(avc1 / 0x31637661)` hold an `x` between digits too, but never after ", ".
_SIZE = re.compile(r', (\d{1,5})x(\d{1,5})(?=[ ,\[]|$)')
_FPS = re.compile(r', (\d+(?:\.\d+)?)(k?) fps')
_ROTATION = re.compile(
    r'(?:rotate\s*:\s*(-?\d+(?:\.\d+)?))|(?:rotation of (-?\d+(?:\.\d+)?) degrees)'
)


def parse(description: str, kind: Optional[str]) -> Probe:
    """Read what ffmpeg said about an input.

    `kind` is the library's kind for the file: `image` has no duration or
    frame rate whatever ffmpeg says (a still has a nominal 25 fps), and
    `audio` has no picture.
    """
    duration = None
    match = _DURATION.search(description)
    if match and kind != 'image':
        hours, minutes, seconds = match.groups()
        duration = round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)

    width = height = fps = None
    stream = _VIDEO_STREAM.search(description)
    if stream and kind != 'audio':
        size = _SIZE.search(stream['description'])
        if size:
            width, height = int(size[1]), int(size[2])
            rotation = _ROTATION.search(description)
            if rotation:
                angle = float(rotation[1] or rotation[2])
                # A quarter turn shows the picture the other way round.
                if round(angle) % 180 == 90:
                    width, height = height, width
        rate = _FPS.search(stream['description'])
        if rate and kind != 'image':
            fps = float(rate[1]) * (1000 if rate[2] else 1)
    return Probe(duration=duration, width=width, height=height, fps=fps)


def ffmpeg_binary() -> str:
    """The ffmpeg the engine encodes with; imported late, as the demo route does."""
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def describe(path) -> str:
    """ffmpeg's description of `path`, or '' if there is none to be had."""
    result = subprocess.run(
        # `file:` so a name is only ever a file, never another protocol.
        [ffmpeg_binary(), '-hide_banner', '-nostdin', '-i', f'file:{path}'],
        capture_output=True,
        text=True,
        errors='replace',
        timeout=PROBE_TIMEOUT,
    )
    return result.stderr or ''


class ProbeCache:
    """Probes of files, by (path, modification time, size); bounded, LRU."""

    def __init__(self, size=CACHE_SIZE):
        self.size = size
        self._entries = OrderedDict()
        self._lock = Lock()

    def get(self, key) -> Optional[Probe]:
        with self._lock:
            probe = self._entries.get(key)
            if probe is not None:
                self._entries.move_to_end(key)
            return probe

    def put(self, key, probe: Probe) -> None:
        with self._lock:
            self._entries[key] = probe
            self._entries.move_to_end(key)
            while len(self._entries) > self.size:
                self._entries.popitem(last=False)

    def __len__(self):
        return len(self._entries)


_cache = ProbeCache()


def probe(path, kind: Optional[str], stat: stat_result) -> Probe:
    """What is known about the file at `path`, from cache when unchanged.

    `stat` is the file's own, which the caller already has. A probe that
    fails -- ffmpeg missing, a file it cannot read -- is UNKNOWN, and cached
    like any other answer, so a broken file is not probed on every listing;
    one that times out is not cached, so it is tried again next time.
    """
    key = (str(path), stat.st_mtime_ns, stat.st_size, kind)
    known = _cache.get(key)
    if known is not None:
        return known
    try:
        result = parse(describe(path), kind)
    except subprocess.TimeoutExpired:
        print(f'probing {path} took longer than {PROBE_TIMEOUT}s', flush=True)
        return UNKNOWN
    except Exception as exc:  # noqa: BLE001 - a probe must never fail a listing
        print(f'could not probe {path}: {exc}', flush=True)
        result = UNKNOWN
    _cache.put(key, result)
    return result
