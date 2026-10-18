"""What the server keeps on disk, and when it lets go of it.

Files were written and never removed: every preview frame, every render's
output and its local delivery copy, every remote file the engine fetched,
outlived whatever made them. And renders finished before RENDER_DIR existed
were written into the media library itself, where they are still listed as
media to everyone.

- `sweep` removes files that have outlived their time: preview frames, and
  the remote media cache (`sweep_remote_cache`, `./al storage cache`).
- `remove_render_files` removes a deleted render's own files.
- `plan_migration` / `apply_migration` move legacy render outputs out of the
  library into RENDER_DIR (`./al storage migrate`).
- `find_orphans` finds render outputs and delivery copies whose render no
  longer exists (`./al storage orphans`).

Run as `python -m alfred.core.utils.storage`, which is what `./al storage`
does inside the api container. Nothing changes without `--apply`.
"""

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from os.path import join
from time import time
from typing import Callable, List, Optional

from bson import ObjectId

from alfred import config

from ..models.render import is_output_filename, output_filename
from .media import LIBRARY_PREFIX, library_file


@dataclass(frozen=True)
class Found:
    """A file a sweep would remove."""

    path: str
    size: int


def expired(
    directory, max_age: float, now: Optional[float] = None, matches: Callable = None
) -> List[Found]:
    """The files in `directory` older than `max_age` seconds.

    Regular files directly inside it only -- never a subdirectory, never a
    symlink -- and only those whose name `matches` accepts, when given. Age is
    the time since the file was last written.
    """
    now = time() if now is None else now
    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        return []
    found = []
    for entry in entries:
        if matches is not None and not matches(entry.name):
            continue
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            info = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        if now - info.st_mtime > max_age:
            found.append(Found(path=entry.path, size=info.st_size))
    return found


def remove(found: List[Found]) -> int:
    """Remove each file; best effort, a failure reported and left. Returns how
    many went."""
    removed = 0
    for item in found:
        try:
            os.unlink(item.path)
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f'could not remove {item.path}: {exc}', flush=True)
    return removed


def sweep(
    directory, max_age: float, now: Optional[float] = None, matches: Callable = None
) -> int:
    """Remove the files in `directory` older than `max_age` seconds.

    As `expired` chooses them. Returns how many were removed.
    """
    return remove(expired(directory, max_age, now=now, matches=matches))


class Every:
    """Due at most once per `interval` seconds; at once if the clock went back."""

    def __init__(self, interval: float):
        self.interval = interval
        self.last = float('-inf')

    def due(self, now: float) -> bool:
        if 0 <= now - self.last < self.interval:
            return False
        self.last = now
        return True


# --- the remote media cache -------------------------------------------------

# What the engine keeps there: `<sha256 of the URL>.<ext>`, and while one is
# being fetched `.<that name>.<random>.part`, which a fetch killed part way can
# leave behind. Nothing else in the directory is touched.
_CACHED = re.compile(r'[0-9a-f]{64}\.[A-Za-z0-9]{1,5}')
_PARTIAL = re.compile(r'\.[0-9a-f]{64}\.[A-Za-z0-9]{1,5}\.[^/]*\.part')

# The most often the cache is swept by the processes that fill it.
REMOTE_CACHE_SWEEP_INTERVAL = 3600

_remote_cache_due = Every(REMOTE_CACHE_SWEEP_INTERVAL)


def is_remote_cache_file(name) -> bool:
    return bool(_CACHED.fullmatch(name) or _PARTIAL.fullmatch(name))


def expired_remote_media(now: Optional[float] = None, max_age=None) -> List[Found]:
    """Fetched remote media older than ALFRED_REMOTE_CACHE_TTL (or `max_age`).

    Age is time since the file was fetched: the engine reuses a cached file
    without touching it, so one in daily use is fetched again once a TTL --
    the price of not tracking every use.
    """
    max_age = config.REMOTE_CACHE_TTL if max_age is None else max_age
    return expired(
        config.REMOTE_CACHE_DIR, max_age, now=now, matches=is_remote_cache_file
    )


def sweep_remote_cache(now: Optional[float] = None, max_age=None) -> int:
    """Remove fetched remote media past its TTL. Returns how many files went.

    The engine fetches each URL a clip names once and keeps it, and nothing
    removed one, so the cache grew for as long as remote media was used.
    """
    return remove(expired_remote_media(now=now, max_age=max_age))


def sweep_remote_cache_now_and_then(now: Optional[float] = None) -> int:
    """`sweep_remote_cache`, at most once an hour: for the paths that fill it."""
    now = time() if now is None else now
    if not _remote_cache_due.due(now):
        return 0
    return sweep_remote_cache(now=now)


# --- a render's own files --------------------------------------------------


def render_files(render_id, filename) -> List[str]:
    """The files that belong to this render and nothing else.

    Its output in RENDER_DIR and the copy a local delivery made, both named
    `<id>.mp4` -- but only when the render's filename is that: a name built
    from the id cannot be anybody else's. A render stored before outputs were
    named by id keeps its old name, which may be a file in the media library
    that people now use as media, so it is never removed from here.
    """
    if not filename or filename != output_filename(render_id):
        return []
    found = []
    for root in (config.RENDER_DIR, config.DELIVERY_DIR):
        path = library_file(filename, root)
        if path is not None:
            found.append(path)
    return found


def remove_render_files(render_id, filename) -> List[str]:
    """Remove a deleted render's files. Best effort; returns what was removed.

    Deleting a render left its video on disk for good, along with any copy a
    delivery made: the record went and the bytes stayed.
    """
    removed = []
    for path in render_files(render_id, filename):
        try:
            os.remove(path)
            removed.append(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f'could not remove {path} of render {render_id}: {exc}', flush=True)
    if removed:
        print(f'removed the files of render {render_id}: {removed}', flush=True)
    return removed


# --- legacy outputs in the library -----------------------------------------


@dataclass
class Move:
    """One legacy render output found in the media library."""

    filename: str
    source: str
    target: str
    size: int
    # The renders whose `filename` names it.
    renders: List[str]
    # Projects and renders that use it as a clip: moving it would break them.
    used_by: List[str] = field(default_factory=list)
    # A file of the same name is already where it would go.
    target_taken: bool = False
    # What happened, once applied.
    outcome: Optional[str] = None

    def movable(self, include_used=False) -> bool:
        return not self.target_taken and (include_used or not self.used_by)

    def why_not(self) -> Optional[str]:
        if self.target_taken:
            return 'a file of that name is already in the render directory'
        if self.used_by:
            return 'used as a clip by ' + ', '.join(self.used_by)
        return None


def _used_by(db, filename) -> List[str]:
    """Who names `videos/<filename>` as a clip."""
    name = LIBRARY_PREFIX + filename
    users = [
        f'project {doc.get("name")!r} ({doc["_id"]})'
        for doc in db.Project.find({'edl.clips.name': name}, {'name': 1})
    ]
    users += [
        f'render {doc["_id"]}'
        for doc in db.Render.find({'edl.clips.name': name}, {'_id': 1})
    ]
    return users


def plan_migration(db, video_dir=None, render_dir=None) -> List[Move]:
    """The legacy render outputs in the library, and what would become of each.

    A file is one when a render's `filename` names it and it sits in the
    library's own directory, where outputs were written before RENDER_DIR. It
    would move to RENDER_DIR, where the download route still finds it and the
    library no longer lists it -- unless a file of that name is there already,
    or a project or render uses it as a clip, which the move would break.
    """
    video_dir = video_dir or config.VIDEO_DIR
    render_dir = render_dir or config.RENDER_DIR
    owners = {}
    for doc in db.Render.find({'filename': {'$type': 'string'}}, {'filename': 1}):
        owners.setdefault(doc['filename'], []).append(str(doc['_id']))

    moves = []
    for filename in sorted(owners):
        source = library_file(filename, video_dir)
        if source is None:
            continue
        move = Move(
            filename=filename,
            source=source,
            target=join(os.path.abspath(render_dir), filename),
            size=os.path.getsize(source),
            renders=owners[filename],
            used_by=_used_by(db, filename),
        )
        move.target_taken = os.path.lexists(move.target)
        moves.append(move)
    return moves


def apply_migration(moves: List[Move], include_used=False) -> List[Move]:
    """Move each planned file that may be moved. Records each outcome."""
    for move in moves:
        if not move.movable(include_used):
            move.outcome = 'skipped'
            continue
        try:
            os.makedirs(os.path.dirname(move.target), exist_ok=True)
            if os.path.lexists(move.target):
                raise FileExistsError(move.target)
            shutil.move(move.source, move.target)
            move.outcome = 'moved'
        except OSError as exc:
            move.outcome = f'failed: {exc}'
    return moves


# --- orphans --------------------------------------------------------------


@dataclass
class Orphan:
    """A render's file whose render no longer exists."""

    path: str
    size: int
    outcome: Optional[str] = None


def find_orphans(db, render_dir=None, delivery_dir=None) -> List[Orphan]:
    """Outputs and delivery copies named for a render that is not stored.

    Every render deleted before deleting removed its files left them behind,
    and a render deleted while its job was still queued is written after the
    delete. Only names built from an id are considered (`<id>.mp4`): anything
    else in these directories is not a render's for certain.
    """
    found = []
    for root in (render_dir or config.RENDER_DIR, delivery_dir or config.DELIVERY_DIR):
        try:
            names = sorted(os.listdir(root))
        except FileNotFoundError:
            continue
        candidates = {
            name: ObjectId(name[:24])
            for name in names
            if is_output_filename(name) and library_file(name, root)
        }
        stored = {
            doc['_id']
            for doc in db.Render.find(
                {'_id': {'$in': list(candidates.values())}}, {'_id': 1}
            )
        }
        for name, render_id in candidates.items():
            if render_id not in stored:
                path = join(os.path.abspath(root), name)
                found.append(Orphan(path=path, size=os.path.getsize(path)))
    return found


def remove_orphans(orphans: List[Orphan]) -> List[Orphan]:
    for orphan in orphans:
        try:
            os.remove(orphan.path)
            orphan.outcome = 'removed'
        except OSError as exc:
            orphan.outcome = f'failed: {exc}'
    return orphans


# --- the command ------------------------------------------------------------


def _size(count) -> str:
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if count < 1024 or unit == 'GB':
            return f'{count:.0f} {unit}' if unit == 'bytes' else f'{count:.1f} {unit}'
        count /= 1024


def _library_name(path, root) -> str:
    """`path` as it reads beside the library: `videos/x.mp4`, `videos/renders/x.mp4`."""
    relative = os.path.relpath(path, os.path.dirname(os.path.abspath(root)))
    return relative.replace(os.sep, '/')


def migrate_command(db, apply=False, include_used=False, out=print) -> int:
    moves = plan_migration(db)
    if not moves:
        out('No render outputs in the media library: nothing to move.')
        return 0
    if apply:
        apply_migration(moves, include_used=include_used)
    movable = [m for m in moves if m.movable(include_used)]
    for move in moves:
        source = _library_name(move.source, config.VIDEO_DIR)
        target = _library_name(move.target, config.VIDEO_DIR)
        if move.outcome:
            verb = move.outcome
        else:
            verb = 'would move' if move.movable(include_used) else 'would skip'
        out(
            f'{verb}: {source} -> {target}  '
            f'({_size(move.size)}; render {", ".join(move.renders)})'
        )
        if move.why_not():
            out(f'    {move.why_not()}')
    if apply:
        moved = [m for m in moves if m.outcome == 'moved']
        failed = [m for m in moves if (m.outcome or '').startswith('failed')]
        out(
            f'Moved {len(moved)} of {len(moves)} files '
            f'({_size(sum(m.size for m in moved))}).'
        )
        return 1 if failed else 0
    out(
        f'Dry run: {len(movable)} of {len(moves)} files '
        f'({_size(sum(m.size for m in movable))}) would move. Nothing was '
        'changed; run with --apply to move them.'
    )
    if not include_used and any(m.used_by and not m.target_taken for m in moves):
        out(
            'Files used as clips are skipped: moving one breaks the projects '
            'that use it. --include-used moves them anyway.'
        )
    return 0


def orphans_command(db, apply=False, out=print) -> int:
    orphans = find_orphans(db)
    if not orphans:
        out('No files left behind by deleted renders.')
        return 0
    if apply:
        remove_orphans(orphans)
    for orphan in orphans:
        verb = orphan.outcome or 'would remove'
        out(f'{verb}: {orphan.path}  ({_size(orphan.size)})')
    total = _size(sum(o.size for o in orphans))
    if apply:
        failed = [o for o in orphans if (o.outcome or '').startswith('failed')]
        out(f'Removed {len(orphans) - len(failed)} of {len(orphans)} files ({total}).')
        return 1 if failed else 0
    out(
        f'Dry run: {len(orphans)} files ({total}) belong to renders that no '
        'longer exist. Nothing was changed; run with --apply to remove them.'
    )
    return 0


def cache_command(apply=False, everything=False, now=None, out=print) -> int:
    found = (
        expired_remote_media(now=now, max_age=-1)
        if everything
        else expired_remote_media(now=now)
    )
    if not found:
        out(
            'Nothing in the remote media cache to remove.'
            if everything
            else 'Nothing in the remote media cache is past its TTL.'
        )
        return 0
    total = _size(sum(f.size for f in found))
    if apply:
        removed = remove(found)
        out(f'Removed {removed} of {len(found)} files ({total}).')
        return 0 if removed == len(found) else 1
    for item in found:
        out(f'would remove: {item.path}  ({_size(item.size)})')
    what = 'files' if everything else 'files past ALFRED_REMOTE_CACHE_TTL'
    out(
        f'Dry run: {len(found)} {what} ({total}). Nothing was changed; run '
        'with --apply to remove them.'
    )
    return 0


def main(argv=None, db=None) -> int:
    parser = argparse.ArgumentParser(
        prog='./al storage',
        description='Tidy what the server keeps on disk. Dry runs by default.',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    migrate = commands.add_parser(
        'migrate',
        help='move render outputs out of the media library into ALFRED_RENDER_DIR',
    )
    migrate.add_argument('--apply', action='store_true', help='move the files')
    migrate.add_argument(
        '--include-used',
        action='store_true',
        help='move files projects use as clips too (breaks those projects)',
    )
    orphans = commands.add_parser(
        'orphans', help='find files whose render has been deleted'
    )
    orphans.add_argument('--apply', action='store_true', help='remove the files')
    cache = commands.add_parser(
        'cache',
        help='remote media the engine fetched, past ALFRED_REMOTE_CACHE_TTL',
    )
    cache.add_argument('--apply', action='store_true', help='remove the files')
    cache.add_argument(
        '--all',
        dest='everything',
        action='store_true',
        help='every cached file, whatever its age (a render using one fails)',
    )
    args = parser.parse_args(argv)

    if args.command == 'cache':
        return cache_command(apply=args.apply, everything=args.everything)
    if db is None:
        from .db import get_sync_db

        db = get_sync_db()
    if args.command == 'migrate':
        return migrate_command(db, apply=args.apply, include_used=args.include_used)
    return orphans_command(db, apply=args.apply)


if __name__ == '__main__':
    sys.exit(main())
