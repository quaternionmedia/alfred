"""Motion in the picture: of a library file, and of a project's timeline.

`GET /media/{name}/motion` has otto measure how much a library file's picture
changes over time (`utils.measures.motion_of`: so many values a second, each
0 to 1) and answers it, kept per version of the file as the audio analyses
are. `GET /project/{id}/motion` maps each file's motion onto a project's
saved timeline through its clips' windows (`utils.sound.levels`, the same
arithmetic as the timeline's sound), so a recipe reads where the picture
moves in timeline seconds.

A still picture, a template and an audio file have no motion: a file with
no moving picture is refused (`no_picture`), and on a timeline such clips
measure 0. Visible to anyone signed in, as the library is; the timeline
route is scoped to the project's owner as every project route is.
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


class FileMotion(BaseModel):
    """`GET /media/{name}/motion`."""

    # How many values a second.
    rate: float
    # Each 0 to 1: how much the picture changed from the moment before.
    values: List[float]


class TimelineMotion(BaseModel):
    """`GET /project/{id}/motion`."""

    duration: float
    rate: float
    values: List[float]


async def library_motion(name: str) -> dict:
    """The motion of library file `name`, from what is kept when the file is
    unchanged. 404 for a file the library does not hold, 422 for one with no
    moving picture (`no_picture`) or whose picture ffmpeg cannot read
    (`picture_unreadable`)."""
    try:
        return await run_in_threadpool(measures.motion_of, name)
    except measures.NotInLibrary as exc:
        raise Refusal(Code.NOT_FOUND, str(exc)) from exc
    except measures.NoPicture as exc:
        raise Refusal(Code.NO_PICTURE, str(exc)) from exc
    except measures.PictureUnreadable as exc:
        raise Refusal(Code.PICTURE_UNREADABLE, str(exc)) from exc


motionAPI = APIRouter()


@motionAPI.get(
    '/media/{name:path}/motion',
    response_model=FileMotion,
    responses={
        404: {'description': 'no such file in the media library'},
        422: {
            'description': 'no moving picture in the file, or one ffmpeg cannot read'
        },
    },
)
async def mediaMotion(name: str):
    """# How a library file's picture moves

    `name` is the file as `GET /media` lists it (`videos/<file>`) or its bare
    file name. Answers `{rate, values}`: `rate` values a second from the start
    of the file, each 0 to 1, how much the picture changed from the moment
    before, as otto measures it from the picture reduced small and grey. A
    still is 0 throughout; a cut is one high value; a camera or a figure that
    moves raises the values while it lasts. Measured once per version of the
    file, which takes minutes for hours of picture, and kept.

    422 for an image or an audio file (`no_picture`) and for a picture ffmpeg
    cannot read (`picture_unreadable`); 404 for what the library does not
    hold (`not_found`).
    """
    return await library_motion(name)


@motionAPI.get(
    '/project/{item_id}/motion',
    response_model=TimelineMotion,
    responses={
        404: {'description': 'no such project, or a file the library does not hold'},
        422: {'description': 'nothing in the saved timeline has a moving picture'},
    },
)
async def getProjectMotion(
    item_id: str,
    user: User = Depends(current_active_user),
    store: SoundStore = Depends(get_sound_store),
):
    """# How a project's picture moves

    `values`, `rate` a second from 0 to `duration`, in timeline seconds: each
    video clip's file measured as `GET /media/{name}/motion` measures it,
    mapped onto the timeline through the clip's window; a still, a template
    and a sound measure 0, and where clips are stacked the one that moves
    most is read.

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
        measured[name] = await library_motion(str(name))
    level = sound.levels(at, measured.get, plays=has_picture)
    return {
        'duration': sound.timeline_end(at),
        'rate': level['rate'],
        'values': level['values'],
    }
