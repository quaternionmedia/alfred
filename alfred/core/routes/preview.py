from fastapi import APIRouter
from ..models.render import Render
from otto.models import Edl
from otto.render import generateEdl
from otto.getdata import timestr
from os.path import join

previewAPI = APIRouter()


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
