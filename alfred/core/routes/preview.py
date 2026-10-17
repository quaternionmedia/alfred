import os
from os import makedirs
from os.path import join
from tempfile import mkstemp
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
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


# Query parameters that describe the frame rather than the template itself.
_FRAME_PARAMS = frozenset({'width', 'height', 't'})


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
    video = generateEdl(timeline, moviesize=(render.width, render.height))
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
    # The allowlist is load-bearing here, not decorative. Without it this is
    # `getattr(templates, name)` on a path segment -- and otto.templates holds
    # imported callables (ColorClip, concatenate_videoclips, rgbToDec) beside
    # its six real templates, so any of those would be reachable by name.
    if name not in TEMPLATE_NAMES:
        raise HTTPException(status_code=404, detail=f'No such template: {name}')

    data = {
        key: value
        for key, value in request.query_params.items()
        if key not in _FRAME_PARAMS and value not in ('null', 'undefined', '')
    }

    clip = Clip(
        type='template',
        name=name,
        duration=max(t, 0) + 1,
        data=TemplateData(**data),
    )

    # A template that cannot render with the data it was given is a 422, not a
    # 500.
    #
    # otto's templates catch their own exceptions and return None, so a
    # missing field does not raise here -- it produces a clip with nothing in
    # it, and the failure surfaces further along when there is no frame to
    # save. `GET /preview/template/title` with no `text` answered 500, which
    # says the server is broken when the truth is that the request was
    # incomplete. The editor showed a blank frame either way.
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
