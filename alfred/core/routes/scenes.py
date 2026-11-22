"""Scene changes in the picture: of a library file, and of a project's timeline.

`GET /media/{name}/scenes` has otto find where a library file's picture cuts
from one shot to another (`utils.measures.scenes_of`: the seconds each new
shot begins at, with the threshold they passed) and answers it, kept per
version of the file as the motion is. `GET /project/{id}/scenes` maps each
file's cuts onto a project's saved timeline through its clips' windows
(`utils.measures.timeline_scenes`), each video clip's own edges among them,
so a recipe reads where a shot begins in timeline seconds.

A still picture, a template and an audio file have no shots: a file with no
moving picture is refused (`no_picture`). Visible to anyone signed in, as
the library is; the timeline route is scoped to the project's owner as every
project route is.
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..errors import Code, Refusal
from ..utils import measures, sound
from ..utils.db import User
from ..utils.measures import has_picture
from .sound import SoundStore, get_sound_store, owned
from .users import current_active_user


class FileScenes(BaseModel):
    """`GET /media/{name}/scenes`."""

    # The scene score, 0 to 1, a frame had to pass.
    threshold: float
    # Each the moment a new shot begins, from the start of the file.
    seconds: List[float]


class TimelineScenes(BaseModel):
    """`GET /project/{id}/scenes`."""

    duration: float
    seconds: List[float]


async def library_scenes(name: str) -> dict:
    """Where library file `name`'s picture cuts, from what is kept when the
    file is unchanged. 404 for a file the library does not hold, 422 for one
    with no moving picture (`no_picture`) or whose picture ffmpeg cannot read
    (`picture_unreadable`)."""
    try:
        return await run_in_threadpool(measures.scenes_of, name)
    except measures.NotInLibrary as exc:
        raise Refusal(Code.NOT_FOUND, str(exc)) from exc
    except measures.NoPicture as exc:
        raise Refusal(Code.NO_PICTURE, str(exc)) from exc
    except measures.PictureUnreadable as exc:
        raise Refusal(Code.PICTURE_UNREADABLE, str(exc)) from exc


scenesAPI = APIRouter()


@scenesAPI.get(
    '/media/{name:path}/scenes',
    response_model=FileScenes,
    responses={
        404: {'description': 'no such file in the media library'},
        422: {
            'description': 'no moving picture in the file, or one ffmpeg cannot read'
        },
    },
)
async def mediaScenes(name: str):
    """# Where a library file's picture cuts

    `name` is the file as `GET /media` lists it (`videos/<file>`) or its bare
    file name. Answers `{threshold, seconds}`: each second the moment a new
    shot begins, from the start of the file, where ffmpeg's scene score
    passed `threshold`, as otto finds them from the picture reduced small
    and grey a few times a second. A hard cut is found at any rate; a slow
    dissolve may or may not pass. Measured once per version of the file,
    which takes minutes for hours of picture, and kept.

    422 for an image or an audio file (`no_picture`) and for a picture ffmpeg
    cannot read (`picture_unreadable`); 404 for what the library does not
    hold (`not_found`).
    """
    return await library_scenes(name)


@scenesAPI.get(
    '/project/{item_id}/scenes',
    response_model=TimelineScenes,
    responses={
        404: {'description': 'no such project, or a file the library does not hold'},
        422: {'description': 'nothing in the saved timeline has a moving picture'},
    },
)
async def getProjectScenes(
    item_id: str,
    user: User = Depends(current_active_user),
    store: SoundStore = Depends(get_sound_store),
):
    """# Where a project's picture cuts

    `seconds`, in timeline seconds from 0 to `duration`: each video clip's
    own start and end, which begin and end a shot, and each scene change of
    its file that falls in the clip's window, as `GET /media/{name}/scenes`
    finds them, moved to where the clip plays it; a still, a template and a
    sound have no shots.

    422 when the saved timeline is empty (`timeline_empty`) or has no video
    clip (`no_picture`); 404 for a file the library does not hold
    (`not_found`), and `picture_unreadable` as the file route answers it.
    """
    project = await owned(store, item_id, user)
    clips = (project.get('edl') or {}).get('clips') or []
    if not clips:
        raise Refusal(
            Code.TIMELINE_EMPTY,
            'The project has no saved timeline to measure; save one first.',
        )
    at = sound.placed(clips)
    moving = [a for a in at if has_picture(a['clip'])]
    if not moving:
        raise Refusal(
            Code.NO_PICTURE,
            'The timeline has no video clip, so there is no moving picture to measure.',
        )
    measured = {}
    for name in dict.fromkeys(a['clip'].get('name') for a in moving):
        measured[name] = await library_scenes(str(name))
    return {
        'duration': sound.timeline_end(at),
        'seconds': measures.timeline_scenes(at, measured.get),
    }
