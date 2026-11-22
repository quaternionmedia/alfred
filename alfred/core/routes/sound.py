"""The sound of a project's timeline, in timeline seconds.

`GET /project/{id}/sound` answers the level over time and the silences of a
project's saved timeline, from the audio engine's analysis of each file it
plays (`routes.audio.library_analysis`, kept per file) mapped onto the
timeline (`utils.sound`). The flow and the recipes hear a timeline through
this route rather than a request per file, and get times they can cut by.

Scoped to the caller the way every project route is (`utils.ownership`): a
project that is not yours answers 404, exactly as one that does not exist.
The route reaches MongoDB only through `SoundStore`, so a test can stand in
for it.
"""

from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..errors import Code, Refusal
from ..models.project import Project
from ..utils import audio_engine, sound
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.db import User
from ..utils.ownership import owner_filter
from .audio import library_analysis
from .users import current_active_user

# Where a project keeps its owner key; see routes.project.
OWNER = 'owner'

# The fields this route reads.
PROJECTION = {'edl': 1}

# What the engine is asked for a timeline's sound.
FEATURES = ('peaks', 'silences')


class Silence(BaseModel):
    start: float
    end: float


class TimelineSound(BaseModel):
    """`GET /project/{id}/sound`."""

    # Where the timeline ends, in seconds.
    duration: float
    # How many levels a second; 0 when nothing was measured.
    rate: float
    # The level over the timeline, 0 to 1, `rate` a second from 0.
    levels: List[float]
    # In timeline seconds, in order.
    silences: List[Silence]


class SoundStore:
    """The project collection, as this route uses it."""

    def _projects(self):
        return Project.get_motor_collection()

    async def find(self, query: dict) -> Optional[dict]:
        return await self._projects().find_one(query, PROJECTION)


def get_sound_store() -> SoundStore:
    return SoundStore()


async def owned(store: SoundStore, item_id: str, user) -> dict:
    """The project `item_id` if `user` may reach it: 422 for a malformed id,
    404 for one not theirs or not there."""
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    project = await store.find({'_id': ObjectId(item_id), **owner_filter(user, OWNER)})
    if project is None:
        raise fresh(NOT_FOUND)
    return project


soundAPI = APIRouter()


@soundAPI.get(
    '/project/{item_id}/sound',
    response_model=TimelineSound,
    responses={
        404: {'description': 'no such project, or a file the library does not hold'},
        422: {'description': 'nothing in the saved timeline to hear'},
        502: {'description': 'the audio engine failed, and why'},
        503: {'description': 'no audio engine to ask, and why'},
    },
)
async def getProjectSound(
    item_id: str,
    user: User = Depends(current_active_user),
    store: SoundStore = Depends(get_sound_store),
):
    """# The sound of a project's timeline

    `levels`, the timeline's level over time, 0 to 1, `rate` a second from
    0, and `silences`, `[{start, end}]`, both in timeline seconds: the audio
    engine's analysis of each file the saved timeline plays, mapped onto the
    timeline through each clip's window. Where clips sound at once, the
    loudest is heard. Each file is analysed once per version and kept.

    422 when the saved timeline is empty (`timeline_empty`) or has no video
    or audio clip (`timeline_silent`); 503 when there is no audio engine
    (`audio_engine_missing`); 404 for a file the library does not hold
    (`not_found`), which a timeline playing remote media is; and the engine's
    own refusals by code, as `GET /media/{name}/audio` answers them.
    """
    project = await owned(store, item_id, user)
    clips = (project.get('edl') or {}).get('clips') or []
    if not clips:
        raise Refusal(
            Code.TIMELINE_EMPTY,
            'The project has no saved timeline to hear; save one first.',
        )
    at = sound.placed(clips)
    heard = [a for a in at if sound.sounding(a['clip'])]
    if not heard:
        raise Refusal(
            Code.TIMELINE_SILENT,
            'The timeline has no video or audio clips, so there is nothing to hear.',
        )
    reason = audio_engine.problem()
    if reason:
        raise Refusal(Code.AUDIO_ENGINE_MISSING, reason)
    analyses = {}
    for name in dict.fromkeys(a['clip'].get('name') for a in heard):
        analyses[name] = await library_analysis(str(name), FEATURES)
    return sound.timeline_sound(clips, analyses)
