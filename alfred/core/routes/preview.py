import json
import os
import re
from os import makedirs
from os.path import abspath, basename, isfile, join, normpath
from tempfile import mkstemp
from time import time
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from otto.exceptions import EdlException
from otto.models import Clip, Edl, TemplateData
from otto.render import renderFrame
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from alfred import config

from ..models.render import Render
from ..utils import storage
from ..utils.concurrency import preview_slot
from ..utils.media import RefusedEdl, resolve_edl
from ..utils.signing import media_url
from .media import MediaAccess, media_access
from .render import refuse_unrenderable
from .templates import TEMPLATE_NAMES

# What `frame_path` names a frame, and all `GET /preview/frames/{name}` serves.
FRAME_NAME = re.compile(r'[0-9a-f]{32}\.jpg')

# Seconds between sweeps as frames are written: previews come many a second.
SWEEP_INTERVAL = 60

# Shared by threads unguarded: two sweeps at once are harmless.
_last_sweep = float('-inf')


def sweep_frames(now=None, force=False) -> int:
    """Remove frames older than ALFRED_FRAME_TTL; how many went. Only names a
    preview makes are touched, whatever else ALFRED_PREVIEW_DIR holds."""
    global _last_sweep
    now = time() if now is None else now
    # A clock that went backwards sweeps rather than waiting to catch up.
    if not force and 0 <= now - _last_sweep < SWEEP_INTERVAL:
        return 0
    _last_sweep = now
    return storage.sweep(
        config.PREVIEW_DIR, config.FRAME_TTL, now=now, matches=FRAME_NAME.fullmatch
    )


async def sweep_frames_at_startup():
    """Sweep frames left from before a restart at once, off the loop."""
    removed = await run_in_threadpool(sweep_frames, force=True)
    if removed:
        print(f'removed {removed} expired preview frames', flush=True)


# Behind the session. Each preview takes a slot first (`preview_slot`).
previewAPI = APIRouter(
    responses={
        503: {'description': 'too many previews at once; ask again after Retry-After'}
    }
)

# Not behind the session: an `<img>` fetches a frame by its signed URL (M1).
previewFrameAPI = APIRouter(on_startup=[sweep_frames_at_startup])


def frame_path():
    """A path in PREVIEW_DIR no concurrent request will also choose: previews
    come many a second, and a shared name serves somebody else's frame."""
    makedirs(config.PREVIEW_DIR, exist_ok=True)
    return join(config.PREVIEW_DIR, f'{uuid4().hex}.jpg')


def frame_url_path(name):
    """Where the frame called `name` is fetched from."""
    return f'/preview/frames/{name}'


def private_frame_path():
    """A temporary file outside every served directory, for a frame that is
    returned in the response itself and not needed afterwards."""
    handle, path = mkstemp(prefix='alfred-frame-', suffix='.jpg')
    os.close(handle)
    return path


def remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


# Query parameters that describe the frame, or the clip around the template,
# rather than the template's own data.
_FRAME_PARAMS = frozenset(
    {'width', 'height', 't', 'fadeIn', 'fadeOut', 'length', 'data'}
)


# A plain function, so it runs in the thread pool, never on the event loop.
@previewAPI.post('/')
@preview_slot
def previewFrame(t: float, render: Render):
    """# Preview frame
    Generates a frame of a given `edl` at time `t`, with `width` and `height`.

    Returns a signed URL for the frame, `/preview/frames/<name>.jpg?exp=…&sig=…`,
    which an `<img>` can use as its `src` until it expires; or a relevant
    error. Frames are kept for ALFRED_FRAME_TTL seconds.
    """
    print('previewing', render.edl, 'at frame', t)
    # A render's checks (C4, the template allowlist) and the worker's
    # resolution, so a clip that previews also renders.
    refuse_unrenderable(render.edl)
    try:
        timeline = resolve_edl(Edl(clips=render.edl.clips))
    except RefusedEdl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # TODO: reduce clips to active clips
    # active = [c for c in render.edl.clips if t >= (c.start or 0) + (c.offset or 0)]
    frame_name = frame_path()
    print(f'saving frame {t} as: {frame_name}')
    try:
        # Builds the whole timeline, refusing a bad clip before writing.
        renderFrame(timeline, t, frame_name, moviesize=(render.width, render.height))
    except EdlException as exc:
        # otto's refusal names the clip (C8): the request's fault, a 422.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sweep_frames()
    # The api fetches remote media here, so it sweeps that cache here.
    storage.sweep_remote_cache_now_and_then()
    # Signed after the session admitted the request.
    return media_url(frame_url_path(basename(frame_name)))


@previewFrameAPI.get(
    '/frames/{name}',
    response_class=FileResponse,
    responses={
        200: {'content': {'image/jpeg': {}}, 'description': 'the frame'},
        401: {'description': 'no session, and no valid signature for this path'},
        404: {'description': 'no such frame, or it has been cleaned up'},
    },
)
async def previewFrameFile(name: str, access: MediaAccess = Depends(media_access)):
    """# A preview frame

    The image `POST /preview/` made, by the signed URL it answered with (or
    with a session). 404 once the frame has been cleaned up.
    """
    missing = HTTPException(
        status_code=404,
        detail='No such preview frame; it may have been cleaned up',
    )
    if not FRAME_NAME.fullmatch(name):
        raise missing
    root = abspath(config.PREVIEW_DIR)
    path = normpath(join(root, name))
    if not path.startswith(join(root, '')) or not isfile(path):
        raise missing
    return FileResponse(path, media_type='image/jpeg')


# A plain function, as `previewFrame` is.
@previewAPI.get('/template/{name}')
@preview_slot
def previewTemplate(
    name: str,
    request: Request,
    width: int = 1920,
    height: int = 1080,
    t: float = 0,
    fadeIn: float = 0,
    fadeOut: float = 0,
    length: Optional[float] = None,
    data: Optional[str] = None,
):
    """# Preview a single template

    Renders one template to a frame and returns the image, so the editor can
    show what a template clip looks like while it is being edited.

    The template's data is `data`, a JSON object, or one query parameter per
    plain field (`?text=Hello`). Nulls are dropped.
    """
    # The allowlist, not otto's registry, which also draws `final`.
    if name not in TEMPLATE_NAMES:
        raise HTTPException(status_code=404, detail=f'No such template: {name}')

    fields = {}
    if data:
        try:
            fields = json.loads(data)
        except ValueError:
            fields = None
        if not isinstance(fields, dict):
            raise HTTPException(status_code=422, detail='data must be a JSON object')
        fields = {key: value for key, value in fields.items() if value is not None}
    fields.update(
        (key, value)
        for key, value in request.query_params.items()
        if key not in _FRAME_PARAMS and value not in ('null', 'undefined', '')
    )

    # No fades unless asked: a clip fades in by default, and the editor
    # samples near the start. Built at the clip's own `length` when given, as
    # a render builds it, since some templates are paced by their length.
    duration = max(t, 0) + 1
    if length is not None and length > 0:
        duration = max(length, max(t, 0) + 0.04)
    clip = Clip(
        type='template',
        name=name,
        duration=duration,
        data=TemplateData(**fields),
        fadeIn=fadeIn,
        fadeOut=fadeOut,
    )

    # Data a template cannot draw from (`title` without `text`) is a 422.
    # The frame goes out in the response, then is deleted.
    frame_name = private_frame_path()
    try:
        renderFrame(Edl(clips=[clip]), t, frame_name, moviesize=(width, height))
    except Exception as exc:
        remove_quietly(frame_name)
        raise HTTPException(
            status_code=422,
            detail=(
                f'{name} could not be rendered from the data supplied. '
                'Templates that take text need it; check the fields on the clip.'
            ),
        ) from exc

    return FileResponse(
        frame_name,
        media_type='image/jpeg',
        background=BackgroundTask(remove_quietly, frame_name),
    )
