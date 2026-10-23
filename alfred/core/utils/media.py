"""What a clip may point at, and where that is on disk.

A `video`, `image` or `audio` clip names its source in `name`, and the engine
opens whatever it is handed: a path relative to the process's working
directory, an absolute path anywhere on the machine, or a URL it downloads.
That made the name a capability the client held over the server. An EDL could
have the worker read `/etc/hostname` (it tried, and failed only because that is
not a video), or fetch any URL the worker can reach.

It also made the library unrenderable. `GET /videos` lists `videos/<file>`,
which the api resolves against its own working directory (`/app`) and the
worker against its own (`/app/alfred`), where there is no `videos/`. So a
clip dragged from the media bin previewed fine and failed every render with
"the file videos/demo-bars.mp4 could not be found".

The rule now (contract C4):

- A media name is either a library path exactly as `GET /videos` lists it,
  `videos/<file>`, or an `http(s)` URL whose host is in
  `ALFRED_REMOTE_MEDIA_HOSTS` (empty by default).
- Absolute paths, `..`, backslashes, control characters, other URL schemes and
  anything resolving outside VIDEO_DIR are refused. The api answers 422.
- Library paths are resolved to `join(VIDEO_DIR, <file>)` here, never against a
  working directory, and the engine is handed the resolved path.

The check and the resolution are one function on purpose: the api validates
with it before queueing, and the worker resolves with it before rendering, so
the two cannot drift apart. The worker repeating the check also covers EDLs
that were stored before it existed and are re-queued later.
"""

import re
from os import listdir
from os.path import abspath, commonpath, isfile, join, realpath, splitext
from typing import Iterable, Optional
from urllib.parse import urlsplit

from alfred import config

# The namespace `GET /videos` lists media under. A literal, not VIDEO_DIR's
# basename: it is part of the API, and moving the directory on disk must not
# change what names a client sends.
LIBRARY_PREFIX = 'videos/'

# Clip types whose `name` is media to open, as opposed to a template to call.
MEDIA_CLIP_TYPES = frozenset({'video', 'image', 'audio'})

# Every clip type the engine renders. Anything else is refused here, when the
# request arrives; the engine refuses it too, but only once a worker has the
# job, after the render has been stored and queued.
CLIP_TYPES = frozenset({'template'}) | MEDIA_CLIP_TYPES

# What the library offers: files a video, image or audio clip can open.
# Anything else in the directory is not media, whoever put it there.
MEDIA_EXTENSIONS = frozenset(
    {
        # video
        '.mp4',
        '.m4v',
        '.mov',
        '.webm',
        '.mkv',
        '.avi',
        '.mpg',
        '.mpeg',
        '.ogv',
        # image
        '.jpg',
        '.jpeg',
        '.png',
        '.gif',
        '.webp',
        '.bmp',
        # audio
        '.mp3',
        '.wav',
        '.m4a',
        '.aac',
        '.ogg',
        '.oga',
        '.flac',
        '.opus',
    }
)

# Files the engine writes beside an output while it encodes, and removes after:
# the audio track otto muxes in (`<output>.audio.m4a`), and moviepy's own
# temporaries. Mid-render they are half-written files with media extensions;
# listed as media, a clip could pick one up.
_ENCODER_TEMPORARIES = re.compile(r'(\.audio\.m4a|TEMP_MPY_\w*\.\w+)$', re.IGNORECASE)

_SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')


class RefusedEdl(ValueError):
    """An EDL asks for something this server will not render.

    The message names the clip and the reason, and is meant for the caller:
    the api answers it as a 422 detail.
    """


class MediaNameError(RefusedEdl):
    """A clip names media this server will not open."""


def is_library_filename(filename) -> bool:
    """Whether `filename` is a name the library can hold, list and serve.

    One path segment, not hidden, no backslash, no control characters, a
    media extension, and not an encoder's temporary file. This is also what
    `GET /videos` lists, so anything it lists is accepted back.
    """
    return (
        isinstance(filename, str)
        and bool(filename)
        and not filename.startswith('.')
        and '/' not in filename
        and '\\' not in filename
        and not _CONTROL.search(filename)
        and splitext(filename)[1].lower() in MEDIA_EXTENSIONS
        and not _ENCODER_TEMPORARIES.search(filename)
    )


def library_file(filename, video_dir=None) -> Optional[str]:
    """The absolute path of a file in the media library, or None.

    None unless `filename` is a plain library name for an existing regular
    file that stays inside VIDEO_DIR once symlinks are followed.
    """
    if not is_library_filename(filename):
        return None
    root = abspath(video_dir or config.VIDEO_DIR)
    path = join(root, filename)
    real_root = realpath(root)
    try:
        inside = commonpath([real_root, realpath(path)]) == real_root
    except ValueError:  # different drives, on Windows
        inside = False
    if not inside or not isfile(path):
        return None
    return path


def output_path(filename, render_dir=None, video_dir=None) -> Optional[str]:
    """Where a render's output file is, or None when there is none to serve.

    Renders are written to RENDER_DIR. One finished before that was so is in
    the media library itself, under the name it was given then, so the library
    is looked in second. Both with the containment a library file has: a
    plain name directly inside the directory, for a regular file that exists.
    A stored name that would leave the directory -- renders stored before
    output was named by id took theirs from the request -- finds nothing.
    """
    for root in (render_dir or config.RENDER_DIR, video_dir or config.VIDEO_DIR):
        path = library_file(filename, root)
        if path is not None:
            return path
    return None


def library_files(video_dir=None) -> list:
    """Every file the library offers, as bare file names, sorted."""
    root = video_dir or config.VIDEO_DIR
    return [name for name in sorted(listdir(root)) if library_file(name, root)]


def check_remote_url(url, remote_hosts: Optional[Iterable[str]] = None) -> str:
    """Accept an http(s) URL on an allowed host; return it unchanged."""
    if not url.startswith(('http://', 'https://')):
        scheme = url.split(':', 1)[0]
        raise MediaNameError(
            f'{url!r}: {scheme}: is not a scheme this server fetches media from. '
            'Name library media as GET /videos lists it (videos/<file>).'
        )
    host = (urlsplit(url).hostname or '').lower()
    allowed = config.REMOTE_MEDIA_HOSTS if remote_hosts is None else remote_hosts
    if not host:
        raise MediaNameError(f'{url!r}: a media URL needs a host')
    if host not in {h.lower() for h in allowed}:
        raise MediaNameError(
            f'{url!r}: remote media from {host} is not allowed on this server. '
            'Use media from the library, or ask an administrator to add the '
            'host to ALFRED_REMOTE_MEDIA_HOSTS.'
        )
    return url


def check_media_name(
    name, video_dir=None, remote_hosts: Optional[Iterable[str]] = None
) -> str:
    """Validate a clip's media name and return what the engine should open.

    A library path comes back as an absolute path under VIDEO_DIR; an allowed
    URL comes back unchanged. Anything else raises MediaNameError with a
    message saying why.
    """
    if not isinstance(name, str) or not name.strip():
        raise MediaNameError('a media clip needs a name: videos/<file> or a URL')
    if _CONTROL.search(name):
        raise MediaNameError(f'{name!r}: control characters are not allowed')
    if '\\' in name:
        raise MediaNameError(f'{name!r}: backslashes are not allowed in media names')
    if _SCHEME.match(name):
        return check_remote_url(name, remote_hosts)
    if name.startswith('/'):
        raise MediaNameError(
            f'{name!r}: absolute paths are not allowed. '
            'Name library media as GET /videos lists it (videos/<file>).'
        )
    if '..' in name.split('/'):
        raise MediaNameError(f'{name!r}: ".." is not allowed in media names')
    if not name.startswith(LIBRARY_PREFIX):
        raise MediaNameError(
            f'{name!r}: not a library path. '
            'Name library media as GET /videos lists it (videos/<file>).'
        )
    filename = name[len(LIBRARY_PREFIX) :]
    if not is_library_filename(filename):
        raise MediaNameError(
            f'{name!r}: not a media file directly inside videos/ '
            '(GET /videos lists the ones there are)'
        )
    path = library_file(filename, video_dir)
    if path is None:
        raise MediaNameError(f'{name!r}: no such file in the media library')
    return path


def check_edl(edl, template_names, video_dir=None, remote_hosts=None) -> None:
    """Refuse an EDL the engine should not be handed. Raises RefusedEdl.

    Checks what the engine would otherwise trust: that there is something to
    render, that every clip has a type it knows, that template clips name an
    allowlisted template, and that media clips name media per C4.

    `template_names` is passed in rather than imported because the allowlist
    lives with the routes, and this module is also imported by the worker,
    which must not drag the whole API in with it.
    """
    if not edl.clips:
        raise RefusedEdl('the timeline has no clips to render')
    for number, clip in enumerate(edl.clips, start=1):
        if clip.type == 'template':
            if clip.name not in template_names:
                raise RefusedEdl(
                    f'clip {number}: {clip.name!r} is not a template this '
                    f'server renders; GET /templates lists them'
                )
        elif clip.type in MEDIA_CLIP_TYPES:
            try:
                check_media_name(clip.name, video_dir, remote_hosts)
            except MediaNameError as exc:
                raise MediaNameError(f'clip {number}: {exc}') from exc
        else:
            raise RefusedEdl(
                f'clip {number}: unknown clip type {clip.type!r}; '
                f'expected one of {sorted(CLIP_TYPES)}'
            )


def resolve_edl(edl, video_dir=None, remote_hosts=None):
    """A copy of `edl` with every media name resolved for the engine.

    Library paths become absolute paths under VIDEO_DIR and allowed URLs pass
    through; anything else raises MediaNameError. The original is left alone,
    so what was stored is what the caller sent.
    """
    resolved = edl.copy(deep=True)
    for number, clip in enumerate(resolved.clips, start=1):
        if clip.type in MEDIA_CLIP_TYPES:
            try:
                clip.name = check_media_name(clip.name, video_dir, remote_hosts)
            except MediaNameError as exc:
                raise MediaNameError(f'clip {number}: {exc}') from exc
    return resolved
