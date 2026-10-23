import os
import re
from os import makedirs
from os.path import basename, isfile, join
from tempfile import mkstemp
from time import time
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from otto.exceptions import EdlException
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl
from starlette.background import BackgroundTask

from alfred import config

from ..models.render import Render
from ..utils import storage
from ..utils.media import RefusedEdl, resolve_edl
from ..utils.signing import media_url
from .media import MediaAccess, media_access
from .render import refuse_unrenderable
from .templates import TEMPLATE_NAMES

# What `frame_path` names a frame, and all `GET /preview/frames/{name}` serves.
FRAME_NAME = re.compile(r'[0-9a-f]{32}\.jpg')

# The most often frames are swept for expiry as new ones are written. The
# editor previews on every playhead move, so sweeping on every write would
# list the directory many times a second for nothing.
SWEEP_INTERVAL = 60

_last_sweep = float('-inf')


def sweep_frames(now=None, force=False) -> int:
    """Remove frames older than ALFRED_FRAME_TTL. Returns how many went.

    Frames were never removed: every playhead move in the editor left one
    behind, for good. Only names a preview makes are touched, so pointing
    ALFRED_PREVIEW_DIR at a directory that holds anything else cannot cost
    that anything.
    """
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
    """Frames left from before a restart are swept at once, not a minute in."""
    removed = sweep_frames(force=True)
    if removed:
        print(f'removed {removed} expired preview frames', flush=True)


# Mounted behind the session.
previewAPI = APIRouter()

# The frames `POST /preview/` makes, on a router of their own: the form flow
# shows one in a bare `<img>`, which carries no session, so it is fetched with
# the signed URL the preview answered with (contract M1).
previewFrameAPI = APIRouter(on_startup=[sweep_frames_at_startup])


def frame_path():
    """A path in PREVIEW_DIR no concurrent request will also choose.

    Both preview routes wrote to `data/<timestr>.jpg`, and `timestr()` is
    second-resolution -- so two previews in the same second produced the same
    filename and one overwrote the other's frame before it was served. The
    editor previews on every playhead move, so concurrent previews are the
    normal case rather than an edge one, and the symptom is a preview showing
    somebody else's frame.

    Found by asking whether the same request twice returns the same bytes. It
    did not: 2049 against 1588.

    Still a name nobody can guess, though it no longer guards anything on its
    own: frames were served by the unauthenticated /data mount, where the
    name was all that stood between a frame and anyone. They are fetched with
    a session or a signed URL now, from a directory nothing serves statically.
    """
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
_FRAME_PARAMS = frozenset({'width', 'height', 't', 'fadeIn', 'fadeOut', 'length'})


@previewAPI.post('/')
async def previewFrame(t: float, render: Render):
    """# Preview frame
    Generates a frame of a given `edl` at time `t`, with `width` and `height`.

    Returns a signed URL for the frame, `/preview/frames/<name>.jpg?exp=…&sig=…`,
    which an `<img>` can use as its `src` until it expires; or a relevant
    error. Frames are kept for ALFRED_FRAME_TTL seconds.
    """
    print('previewing', render.edl, 'at frame', t)
    # The same checks as a render (C4 and the template allowlist), then the
    # same resolution the worker does. Previewing opened clip names against
    # the api's working directory, which happens to hold `videos/` -- so a
    # clip previewed fine and then failed to render -- and opened absolute
    # paths and fetched URLs exactly as sent.
    refuse_unrenderable(render.edl)
    try:
        timeline = resolve_edl(Edl(clips=render.edl.clips))
    except RefusedEdl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # TODO: reduce clips to active clips
    # active = [c for c in render.edl.clips if t >= (c.start or 0) + (c.offset or 0)]
    try:
        video = generateEdl(timeline, moviesize=(render.width, render.height))
    except EdlException as exc:
        # The engine's own refusal of a clip it cannot build (contract C8) is
        # the request's fault, and names the clip: a 422 with that message,
        # not a 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    frame_name = frame_path()
    print(f'saving frame {t} as: {frame_name}', video)
    video.save_frame(frame_name, t=t, withmask=False)
    sweep_frames()
    # A preview is where the api fetches remote media, so it is where the
    # api keeps that cache within its TTL.
    storage.sweep_remote_cache_now_and_then()
    # Signed here, after the caller's session admitted the request: the URL is
    # how the frame reaches an `<img>`. It was a path under the public /data
    # mount.
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
    path = join(config.PREVIEW_DIR, name)
    if not FRAME_NAME.fullmatch(name) or not isfile(path):
        raise HTTPException(
            status_code=404,
            detail='No such preview frame; it may have been cleaned up',
        )
    return FileResponse(path, media_type='image/jpeg')


@previewAPI.get('/template/{name}')
async def previewTemplate(
    name: str,
    request: Request,
    width: int = 1920,
    height: int = 1080,
    t: float = 0,
    fadeIn: float = 0,
    fadeOut: float = 0,
    length: Optional[float] = None,
):
    """# Preview a single template

    Renders one template to a frame and returns the image, so the editor can
    show what a template clip looks like while it is being edited.

    The editor has requested this since before it existed: `Preview.js` builds
    `otto/template/{name}?...` as an `<img src>`, and it 404'd on every render
    of a template clip. It is a GET returning an image rather than the
    POST-and-filename shape of `/preview/` above, because that is what an
    `<img>` can consume.

    Template parameters arrive as query parameters, which the editor already
    sends. Anything not named here is passed to the template as data; `null`
    is dropped rather than forwarded, since the editor serialises absent
    fields that way and the template expects them missing.
    """
    # The allowlist, not the engine's registry: the engine refuses anything
    # that is not a template, but it also renders `final`, which this server
    # does not offer (see routes/templates.py). A name that is not offered is
    # a missing resource.
    if name not in TEMPLATE_NAMES:
        raise HTTPException(status_code=404, detail=f'No such template: {name}')

    data = {
        key: value
        for key, value in request.query_params.items()
        if key not in _FRAME_PARAMS and value not in ('null', 'undefined', '')
    }

    # No fades unless the request asks for them. A clip fades in over its
    # first second by default, so a preview sampled near the start -- which is
    # where the editor samples a template it has just placed -- came out dimmed
    # or black, rather than showing the template as it looks on screen.
    # Built at the clip's own length when the editor says what it is (`length`:
    # its outpoint, or its duration), the way a render builds it. A template
    # paced by its length -- title's box reveal -- drew a different frame at the
    # same `t` when it was built one second past `t`, which is what the second
    # half of a cut or a slipped template showed.
    duration = max(t, 0) + 1
    if length is not None and length > 0:
        duration = max(length, max(t, 0) + 0.04)
    clip = Clip(
        type='template',
        name=name,
        duration=duration,
        data=TemplateData(**data),
        fadeIn=fadeIn,
        fadeOut=fadeOut,
    )

    # A template that cannot render with the data it was given is a 422, not a
    # 500: the request is incomplete, the server is not broken. The engine
    # raises for it -- `GET /preview/template/title` with no `text` is an
    # EdlException naming the template and the missing argument. (Its
    # templates used to swallow the error and return None, and the failure
    # surfaced as a 500 when there was no frame to save.)
    #
    # Written privately and deleted once sent. This route returns the image
    # itself, so nothing needs the file afterwards -- and it was written under
    # DATA_DIR, which the unauthenticated /data mount served, and kept there
    # for good: every frame anyone previewed stayed public.
    frame_name = private_frame_path()
    try:
        video = generateEdl(Edl(clips=[clip]), moviesize=(width, height))
        video.save_frame(frame_name, t=t, withmask=False)
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
