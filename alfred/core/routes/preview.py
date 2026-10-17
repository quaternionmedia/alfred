import os
from os import makedirs
from os.path import join
from tempfile import mkstemp
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from otto.exceptions import EdlException
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl
from starlette.background import BackgroundTask

from alfred.config import DATA_DIR

from ..models.render import Render
from ..utils.media import RefusedEdl, resolve_edl
from .render import refuse_unrenderable
from .templates import TEMPLATE_NAMES

previewAPI = APIRouter()


def frame_path():
    """A path no concurrent request will also choose.

    Both preview routes wrote to `data/<timestr>.jpg`, and `timestr()` is
    second-resolution -- so two previews in the same second produced the same
    filename and one overwrote the other's frame before it was served. The
    editor previews on every playhead move, so concurrent previews are the
    normal case rather than an edge one, and the symptom is a preview showing
    somebody else's frame.

    Found by asking whether the same request twice returns the same bytes. It
    did not: 2049 against 1588.

    And a name nobody can guess, because the name is all that stands between
    a frame and anyone who asks for it: DATA_DIR is served by an
    unauthenticated static mount, which is how the form flow's preview shows
    the frame in an `<img>`. It was a second-resolution timestamp and eight
    hex digits -- every frame made in a given second was one of four billion
    names. A random UUID alone is 122 bits.
    """
    makedirs(DATA_DIR, exist_ok=True)
    return join(DATA_DIR, f'{uuid4().hex}.jpg')


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
_FRAME_PARAMS = frozenset({'width', 'height', 't', 'fadeIn', 'fadeOut'})


@previewAPI.post('/')
async def previewFrame(t: float, render: Render):
    """# Preview frame
    Generates a frame of a given `edl` at time `t`, with `width` and `height`.

     Returns the name of a file on this server when available, or a relevant error
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
    return frame_name


@previewAPI.get('/template/{name}')
async def previewTemplate(
    name: str,
    request: Request,
    width: int = 1920,
    height: int = 1080,
    t: float = 0,
    fadeIn: float = 0,
    fadeOut: float = 0,
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
    clip = Clip(
        type='template',
        name=name,
        duration=max(t, 0) + 1,
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
    # DATA_DIR, which the unauthenticated /data mount serves, and kept there
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
