from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from ..models.render import Render
from otto.models import Edl, Clip, TemplateData
from otto.render import generateEdl
from otto.getdata import timestr
from os.path import join

from .templates import TEMPLATE_NAMES

previewAPI = APIRouter()

# Query parameters that describe the frame rather than the template itself.
_FRAME_PARAMS = frozenset({'width', 'height', 't'})


@previewAPI.post('/')
async def previewFrame(t: float, render: Render):
    """# Preview frame
    Generates a frame of a given `edl` at time `t`, with `width` and `height`.

     Returns the name of a file on this server when available, or a relevant error
    """
    print('previewing', render.edl, 'at frame', t)
    # TODO: reduce clips to active clips
    # active = [c for c in render.edl.clips if t >= (c.start or 0) + (c.offset or 0)]
    video = generateEdl(
        Edl(clips=render.edl.clips), moviesize=(render.width, render.height)
    )
    frame_name = join('data', timestr() + '.jpg')
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
    video = generateEdl(Edl(clips=[clip]), moviesize=(width, height))

    frame_name = join('data', timestr() + '.jpg')
    video.save_frame(frame_name, t=t, withmask=False)
    return FileResponse(frame_name, media_type='image/jpeg')
