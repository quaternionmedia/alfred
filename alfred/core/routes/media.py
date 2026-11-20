"""Media: who may fetch a file, and what the library holds.

`media_access` is the half of contract M1 a route depends on: a session, or
a valid, unexpired signature for exactly the path asked for (`utils.signing`).
The file routes (`GET /render/{id}/download`, `GET /videos/{name}`, `GET
/preview/frames/{name}`) depend on it, so a browser can fetch them by itself.
It is here, not in `utils`, because the worker imports `utils` and must not
import routes.

`GET /media` is contract M2: the library as `GET /videos` lists it, with what
the editor needs to place each file -- its kind, how long it runs, its size
in pixels -- and a signed URL to load it from. `POST /media` puts a file of
the caller's own into the library, and `DELETE /media/{name}` takes one out:
the library is the server's, as the listing is, so anyone signed in may.
"""

import os
from dataclasses import dataclass
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from alfred import config
from alfred.config import DEV_SKIP_AUTH

from ..errors import Code, Refusal
from ..utils import signing, storage
from ..utils.media import (
    LIBRARY_PREFIX,
    MEDIA_EXTENSIONS,
    is_library_filename,
    library_file,
    library_files,
    media_kind,
)
from ..utils.probe import probe
from .users import fastapi_users, get_dev_user

# The session's user, or None: `current_active_user` would answer 401 before
# the signature is looked at. Under the auth bypass, the dev user.
optional_user = (
    get_dev_user
    if DEV_SKIP_AUTH
    else fastapi_users.current_user(active=True, optional=True)
)

UNAUTHORIZED = 'Unauthorized'
REFUSED = {
    signing.EXPIRED: 'This media link has expired; ask for a new one',
    signing.INVALID: 'This media link is not valid',
}


@dataclass(frozen=True)
class MediaAccess:
    """How a request for a file was admitted.

    `signed` when it carried a good signature for its path: a capability the
    server issued after its own checks, so the route does not repeat them.
    Otherwise `user` is the session's user, and the route applies its usual
    ownership rules to them.
    """

    user: Optional[Any]
    signed: bool


async def media_access(request: Request, user=Depends(optional_user)) -> MediaAccess:
    """Admit a session, or a valid signature for this exact path; else 401."""
    params = request.query_params
    if 'sig' in params or 'exp' in params:
        problem = signing.check(
            signing.route_path(request.scope), params.get('exp'), params.get('sig')
        )
        if problem is None:
            return MediaAccess(user=user, signed=True)
        if user is None:
            raise HTTPException(status_code=401, detail=REFUSED[problem])
    if user is not None:
        return MediaAccess(user=user, signed=False)
    raise HTTPException(status_code=401, detail=UNAUTHORIZED)


class MediaItem(BaseModel):
    """One file in the library (contract M2)."""

    # As a clip names it, and as `GET /videos` lists it: `videos/<file>`.
    name: str
    kind: Literal['video', 'image', 'audio']
    # Seconds; null for an image, and for anything ffmpeg could not read.
    duration: Optional[float] = None
    # The picture's size as shown, a quarter-turn rotation applied; null for
    # audio.
    width: Optional[int] = None
    height: Optional[int] = None
    # Frames a second; null for images and audio.
    fps: Optional[float] = None
    # Bytes on disk.
    size: int
    # A signed URL for the file, which a `<video>` or `<img>` can use as its
    # `src` until it expires (contract M1).
    url: str


def describe_file(name, root) -> Optional[MediaItem]:
    """One library file, described; None once it is gone. Blocking: probes."""
    path = library_file(name, root)
    try:
        stat = os.stat(path) if path else None
    except FileNotFoundError:
        stat = None
    if stat is None:
        return None
    kind = media_kind(name)
    found = probe(path, kind, stat)
    return MediaItem(
        name=LIBRARY_PREFIX + name,
        kind=kind,
        duration=found.duration,
        width=found.width,
        height=found.height,
        fps=found.fps,
        size=stat.st_size,
        url=signing.media_url(f'/videos/{name}'),
    )


def describe_library(video_dir=None) -> List[MediaItem]:
    """Every file `GET /videos` lists, described. Blocking: probes files."""
    root = video_dir or config.VIDEO_DIR
    os.makedirs(root, exist_ok=True)
    items = []
    for name in library_files(root):
        item = describe_file(name, root)
        # Gone between the listing and now: left out.
        if item is not None:
            items.append(item)
    return items


# The most an upload may be, in bytes: a feature at broadcast quality fits.
UPLOAD_LIMIT = 4 * 1024**3
# Copied this much at a time, so a large upload never sits whole in memory.
CHUNK = 1024 * 1024
# What a file is called while it arrives: not a media extension, so the
# library never lists a file half written.
ARRIVING = '.uploading'

NOT_IN_LIBRARY = 'No such file in the media library'


class TooLarge(Exception):
    pass


def store_upload(source, path: str, limit: int = UPLOAD_LIMIT) -> int:
    """Copy `source`, a file object, to `path` through a file named for its
    arrival, which takes the name only once the whole of it is there. The
    bytes written; TooLarge, and nothing left behind, past `limit`.
    Blocking: run in the thread pool."""
    arriving = path + ARRIVING
    written = 0
    try:
        with open(arriving, 'wb') as out:
            while chunk := source.read(CHUNK):
                written += len(chunk)
                if written > limit:
                    raise TooLarge()
                out.write(chunk)
        os.replace(arriving, path)
    finally:
        if os.path.exists(arriving):
            os.remove(arriving)
    return written


class MediaDeleted(BaseModel):
    """`DELETE /media/{name}`: the file that is gone."""

    name: str


async def sweep_remote_cache_at_startup():
    """Fetched remote media past its TTL goes when the api starts.

    Then at most hourly as previews and renders fetch more; see
    `storage.sweep_remote_cache_now_and_then`.
    """
    removed = await run_in_threadpool(storage.sweep_remote_cache)
    if removed:
        print(f'removed {removed} expired files from the remote media cache')


# Mounted behind the session.
mediaAPI = APIRouter(on_startup=[sweep_remote_cache_at_startup])


@mediaAPI.get('/media', response_model=List[MediaItem])
async def listMedia():
    """# Media

    The media library, with what is known about each file: `kind` (`video`,
    `image` or `audio`), `duration` in seconds, `width` and `height` in
    pixels, `fps`, `size` in bytes, and `url`, a signed URL a `<video>` or
    `<img>` can load it from directly. Anything that cannot be known is null.

    The same files as `GET /videos`, which keeps its list of names. Files are
    probed once and remembered until they change, so the first listing of a
    large library is the slow one.
    """
    return await run_in_threadpool(describe_library)


@mediaAPI.post(
    '/media',
    response_model=MediaItem,
    status_code=201,
    responses={
        409: {'description': 'a file of that name is in the library already'},
        413: {'description': 'larger than an upload may be'},
        422: {'description': 'not a name the library can hold'},
    },
)
async def uploadMedia(file: UploadFile, replace: bool = False):
    """# Add a file to the library

    A multipart upload, `file`, kept under its own file name: one path
    segment with a media extension, as `GET /videos` lists names. Answers
    the file as `GET /media` describes it, probed. A name the library holds
    already is refused (`media_exists`) unless `replace=true`, in which
    case the file is replaced; a name the library cannot hold is refused
    (`media_name_refused`), as is a file past the upload limit
    (`media_too_large`). The file takes its name only once the whole of it
    has arrived, so a listing never shows a file half written.
    """
    name = os.path.basename(file.filename or '')
    if not is_library_filename(name):
        raise Refusal(
            Code.MEDIA_NAME_REFUSED,
            f'{name!r} is not a name the library can hold: one file name, not '
            f'hidden, ending in one of {", ".join(sorted(MEDIA_EXTENSIONS))}',
        )
    root = os.path.abspath(config.VIDEO_DIR)
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, name)
    if os.path.exists(path) and not replace:
        raise Refusal(
            Code.MEDIA_EXISTS,
            f'{LIBRARY_PREFIX}{name} is in the library already; send replace=true '
            'to replace it',
        )
    try:
        # The limit read now, not when the helper was defined: a test moves it.
        await run_in_threadpool(store_upload, file.file, path, UPLOAD_LIMIT)
    except TooLarge:
        raise Refusal(
            Code.MEDIA_TOO_LARGE,
            f'{name} is larger than an upload may be, {UPLOAD_LIMIT} bytes',
        ) from None
    finally:
        await file.close()
    item = await run_in_threadpool(describe_file, name, root)
    if item is None:
        raise Refusal(Code.NOT_FOUND, NOT_IN_LIBRARY)
    return item


@mediaAPI.delete(
    '/media/{name:path}',
    response_model=MediaDeleted,
    responses={404: {'description': 'no such file in the media library'}},
)
async def deleteMedia(name: str):
    """# Take a file out of the library

    `name` is the file as `GET /media` lists it (`videos/<file>`) or its bare
    file name. The file is removed; a timeline that names it will not play
    or render until it is put back. 404 (`not_found`) for what the library
    does not hold.
    """
    filename = name[len(LIBRARY_PREFIX) :] if name.startswith(LIBRARY_PREFIX) else name
    path = library_file(filename, config.VIDEO_DIR)
    if path is None:
        raise Refusal(Code.NOT_FOUND, NOT_IN_LIBRARY)
    await run_in_threadpool(os.remove, path)
    return MediaDeleted(name=LIBRARY_PREFIX + filename)
