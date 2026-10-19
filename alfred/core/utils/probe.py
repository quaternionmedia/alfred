"""How long a media file runs, and how big its picture is (contract M2).

The editor added every library clip to the timeline as five seconds long,
because nothing on the server would say how long a file was. The engine says
now -- `otto.media.probe` asks the ffmpeg otto encodes with to describe the
file, decoding nothing -- and this keeps the answer, so a listing does not
start a process per file every time.

What a file holds is otto's to say; when to ask again is alfred's. Answers are
cached by the file's path, modification time and size, so an edited or
replaced file is probed again and an unchanged one never is. The cache is
bounded.
"""

from collections import OrderedDict
from os import stat_result
from threading import Lock
from typing import Optional

from otto.media import PROBE_TIMEOUT, UNKNOWN, MediaInfo
from otto.media import probe as probe_file

# Entries kept, most recently used first out last. A library listing touches
# every file, so this bounds memory for libraries larger than it, at the cost
# of probing them again.
CACHE_SIZE = 2048


class ProbeCache:
    """Probes of files, by (path, modification time, size); bounded, LRU."""

    def __init__(self, size=CACHE_SIZE):
        self.size = size
        self._entries = OrderedDict()
        self._lock = Lock()

    def get(self, key) -> Optional[MediaInfo]:
        with self._lock:
            probe = self._entries.get(key)
            if probe is not None:
                self._entries.move_to_end(key)
            return probe

    def put(self, key, probe: MediaInfo) -> None:
        with self._lock:
            self._entries[key] = probe
            self._entries.move_to_end(key)
            while len(self._entries) > self.size:
                self._entries.popitem(last=False)

    def __len__(self):
        return len(self._entries)


_cache = ProbeCache()


def probe(path, kind: Optional[str], stat: stat_result) -> MediaInfo:
    """What is known about the file at `path`, from cache when unchanged.

    `kind` is the library's kind for the file -- `video`, `image` or `audio`,
    the type of clip that opens it -- which tells the engine what to leave
    out: an image has no duration or frame rate, audio no picture. `stat` is
    the file's own, which the caller already has. A probe that fails --
    ffmpeg missing, a file it cannot read -- is UNKNOWN, and cached like any
    other answer, so a broken file is not probed on every listing; one that
    times out is not cached, so it is tried again next time.
    """
    key = (str(path), stat.st_mtime_ns, stat.st_size, kind)
    known = _cache.get(key)
    if known is not None:
        return known
    try:
        result = probe_file(path, kind)
    except TimeoutError:
        print(f'probing {path} took longer than {PROBE_TIMEOUT}s', flush=True)
        return UNKNOWN
    except Exception as exc:  # noqa: BLE001 - a probe must never fail a listing
        print(f'could not probe {path}: {exc}', flush=True)
        result = UNKNOWN
    _cache.put(key, result)
    return result
