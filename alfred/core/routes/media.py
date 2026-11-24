"""Media: who may fetch a file, and what the library holds.

`media_access` is the half of contract M1 a route depends on: it admits a
request carrying a session (as every route did), or one carrying a valid,
unexpired signature for exactly the path it asks for (see `utils.signing`).
The routes that serve files -- `GET /render/{id}/download`, `GET
/videos/{name}` and `GET /preview/frames/{name}` -- depend on it instead of on
the session alone, so the browser can fetch them by itself from `<video>`,
`<img>` and `<a download>`.

It lives here rather than beside the signing code because it needs the
session dependency from the routes layer, and `utils` is imported by the
worker, which has no business importing routes.

`GET /media` is contract M2: the library as `GET /videos` lists it, with what
the editor needs to place each file -- its kind, how long it runs, its size
in pixels -- and a signed URL to load it from.
"""

import os
from dataclasses import dataclass
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from alfred import config
from alfred.config import DEV_SKIP_AUTH

from ..utils import signing, storage
from ..utils.media import LIBRARY_PREFIX, library_file, library_files, media_kind
from ..utils.probe import probe
from .users import fastapi_users, get_dev_user

# The session's user, or None when the request has no valid session. The
# media routes cannot use `current_active_user`, which answers 401 before the
# route can look for a signature. Under the dev auth bypass every request has
# the dev user, as on every other route.
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


def describe_library(video_dir=None) -> List[MediaItem]:
    """Every file `GET /videos` lists, described. Blocking: probes files."""
    root = video_dir or config.VIDEO_DIR
    os.makedirs(root, exist_ok=True)
    items = []
    for name in library_files(root):
        path = library_file(name, root)
        try:
            stat = os.stat(path) if path else None
        except FileNotFoundError:
            stat = None
        if stat is None:
            # Gone between the listing and now.
            continue
        kind = media_kind(name)
        found = probe(path, kind, stat)
        items.append(
            MediaItem(
                name=LIBRARY_PREFIX + name,
                kind=kind,
                duration=found.duration,
                width=found.width,
                height=found.height,
                fps=found.fps,
                size=stat.st_size,
                url=signing.media_url(f'/videos/{name}'),
            )
        )
    return items


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
