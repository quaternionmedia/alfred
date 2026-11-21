"""The engines' analyses of library files, kept on disk between processes.

An analysis of a file is worth keeping: the audio engine's reading of a
long recording's sound costs it a decode of the whole file, and otto's
measure of its motion costs a decode of every frame. The api keeps each in
memory while it runs (`utils.probe.ProbeCache`), and here beside the library
too, so an api that has restarted, or the worker, which never asked, reads
what was measured rather than measuring again. A file that changes is
measured again: the key names its path, its modification time and its size,
with what was asked of it.

Kept under `<VIDEO_DIR>/.analyses/`, a hidden folder the library never lists
(`utils.media.is_library_filename`), one JSON file per key. Anything that
goes wrong reading or writing one is a cache miss, never a failure.
"""

import hashlib
import json
import os
import tempfile
from os.path import join
from typing import Any, Optional

from alfred import config

FOLDER = '.analyses'


def directory(video_dir=None) -> str:
    return join(video_dir or config.VIDEO_DIR, FOLDER)


def _name(key) -> str:
    digest = hashlib.sha256(
        json.dumps(key, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f'{digest[:40]}.json'


def get(key, video_dir=None) -> Optional[Any]:
    """What was kept under `key`, or None."""
    try:
        with open(join(directory(video_dir), _name(key)), encoding='utf-8') as file:
            kept = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(kept, dict) or kept.get('key') != json.loads(
        json.dumps(key, default=str)
    ):
        return None
    return kept.get('analysis')


def put(key, analysis, video_dir=None) -> None:
    """Keep `analysis` under `key`: written whole, then moved into place, so a
    reader never meets half a file."""
    folder = directory(video_dir)
    try:
        os.makedirs(folder, exist_ok=True)
        handle, partial = tempfile.mkstemp(prefix='.', suffix='.part', dir=folder)
        with os.fdopen(handle, 'w', encoding='utf-8') as file:
            json.dump({'key': key, 'analysis': analysis}, file, default=str)
        os.replace(partial, join(folder, _name(key)))
    except (OSError, TypeError, ValueError) as exc:
        print(f'could not keep an analysis under {folder}: {exc}', flush=True)
