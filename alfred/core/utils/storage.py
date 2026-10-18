"""What the server keeps on disk, and when it lets go of it.

Files were written and never removed: every preview frame, every render's
output and its local delivery copy outlived whatever made them.
"""

import os
from time import time
from typing import Callable, Optional


def sweep(
    directory, max_age: float, now: Optional[float] = None, matches: Callable = None
) -> int:
    """Remove the files in `directory` older than `max_age` seconds.

    Regular files directly inside it only -- never a subdirectory, never a
    symlink -- and only those whose name `matches` accepts, when given. Age is
    the time since the file was last written. Best effort: a file that cannot
    be removed is reported and left. Returns how many were removed.
    """
    now = time() if now is None else now
    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        return 0
    removed = 0
    for entry in entries:
        if matches is not None and not matches(entry.name):
            continue
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            if now - entry.stat(follow_symlinks=False).st_mtime <= max_age:
                continue
            os.unlink(entry.path)
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f'could not remove {entry.path}: {exc}', flush=True)
    return removed
