"""Cues on a project: read them, and write them -- all of them, or one
writer's. The editor draws them on its timeline (the Cues lane); a program
driving the editor places them, as qmcp's excerpt flow places the stretches
it proposes and says where each stands.

Every route is scoped to the caller the way every project route is
(`utils.ownership`): a project that is not yours answers 404, exactly as one
that does not exist. The routes reach MongoDB only through `CuesStore`, so a
test can stand in for it.
"""

from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, ValidationError

from ..errors import Code, Refusal
from ..models.cues import MAX_SOURCE_CHARS, Cue, TooManyCues, checked_cues, one_line
from ..models.project import Project
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.db import User
from ..utils.ownership import owner_filter
from .users import current_active_user

# Where a project keeps its owner key; see routes.project.
OWNER = 'owner'

# The fields these routes read.
PROJECTION = {'cues': 1}


class CuesView(BaseModel):
    """`GET /project/{id}/cues`."""

    cues: List[Cue]


class CuesUpdate(BaseModel):
    """`PUT /project/{id}/cues`: the cues, and whose they are."""

    cues: List[Cue]
    # Given, the cues replace this source's and are stamped with it; left
    # out, they replace every cue the project holds.
    source: Optional[str] = None

    model_config = ConfigDict(extra='forbid')


class CuesStore:
    """The project collection, as these routes use it."""

    def _projects(self):
        return Project.get_motor_collection()

    async def find(self, query: dict) -> Optional[dict]:
        return await self._projects().find_one(query, PROJECTION)

    async def set(self, project_id, fields: dict) -> None:
        await self._projects().update_one({'_id': project_id}, {'$set': fields})


def get_cues_store() -> CuesStore:
    return CuesStore()


async def owned(store: CuesStore, item_id: str, user) -> dict:
    """The project `item_id` if `user` may reach it: 422 for a malformed id,
    404 for one not theirs or not there."""
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    project = await store.find({'_id': ObjectId(item_id), **owner_filter(user, OWNER)})
    if project is None:
        raise fresh(NOT_FOUND)
    return project


def cues_of(project: dict) -> List[Cue]:
    """A stored project's cues, each as it validates; one stored by something
    that skipped the checks is left out rather than failing the whole read."""
    cues = []
    for stored in project.get('cues') or []:
        try:
            cues.append(Cue.model_validate(stored))
        except ValidationError as exc:
            print('skipping a stored cue that does not validate:', exc)
    return cues


cuesAPI = APIRouter()


@cuesAPI.get('/project/{item_id}/cues', response_model=CuesView)
async def getProjectCues(
    item_id: str,
    user: User = Depends(current_active_user),
    store: CuesStore = Depends(get_cues_store),
):
    """# A project's cues

    `cues`, each `{start, end, label, kind, state, source, ref, note}` in
    timeline seconds and in order of when they start. A cue with no `end` is
    a point. `kind` says what sort of cue it is (`chapter`, `excerpt`, `mark`,
    or a writer's own word), `state` where it stands with its writer (an
    excerpt the harness proposed is `proposed`, then `waiting`, `approved` or
    `rejected`, then `rendered` and `delivered`), `source` who wrote it, `ref`
    their reference and `note` what a reader may want to know. Empty until
    something writes them.
    """
    return CuesView(cues=cues_of(await owned(store, item_id, user)))


@cuesAPI.put('/project/{item_id}/cues', response_model=CuesView)
async def saveProjectCues(
    item_id: str,
    update: CuesUpdate,
    user: User = Depends(current_active_user),
    store: CuesStore = Depends(get_cues_store),
):
    """# Save a project's cues

    With a `source`, replaces the cues that source wrote with `cues`, each
    stamped with it, and keeps every other writer's; without one, replaces
    every cue the project holds with `cues`, each keeping the source it
    carries. Nothing else on the project is written. Each cue starts at or
    after 0, ends no earlier than it starts when it ends at all, and has a
    label of at most 200 characters; `kind` and `state` are words of letters,
    digits, hyphens and underscores. They are stored in order of when they
    start, at most 2000 to a project. Answers `{cues}` as stored.
    """
    project = await owned(store, item_id, user)
    source = (
        one_line(update.source, 'source', MAX_SOURCE_CHARS) if update.source else None
    )
    sent = update.cues
    kept = cues_of(project)
    if source:
        sent = [cue.model_copy(update={'source': source}) for cue in sent]
        kept = [cue for cue in kept if cue.source != source]
    else:
        kept = []
    try:
        cues = checked_cues(kept + sent)
    except TooManyCues as exc:
        raise Refusal(Code.TOO_MANY_CUES, str(exc)) from exc
    await store.set(project['_id'], {'cues': [cue.model_dump() for cue in cues]})
    return CuesView(cues=cues)
