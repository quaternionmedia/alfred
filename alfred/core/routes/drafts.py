"""A source's drafts: start a run of recipes over a project, list what it
left, and drop what is not wanted.

`POST /project/{id}/drafts` queues a run the worker makes
(`utils.tasks.sculptDrafts`, `utils.drafts.make_drafts`), recorded on the
source as its `drafts_job`; `GET /project/{id}/drafts` lists the job and the
drafts, each a project carrying `source`; `DELETE /project/{id}/drafts` drops
the drafts named, and nothing that is not one of this source's drafts, and
leaves on the source what it keeps of each (`drafts_dropped`), so a recipe's
values can be measured against what people keep and drop (`utils.measured`).

Every route is scoped to the caller the way every project route is
(`utils.ownership`): a project that is not yours answers 404, exactly as one
that does not exist. The routes reach MongoDB only through `DraftsStore` and
Celery only through `get_drafts_queue`, so a test can stand in for either.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..errors import Code, Refusal
from ..models.drafts import RUNNING, DraftsJob, DraftSource
from ..models.project import Project
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.db import User
from ..utils.ownership import owner_filter
from ..utils.tasks import sculptDrafts
from .recipes import RecipeStore, find_recipe, get_recipe_store
from .users import current_active_user

OWNER = 'owner'

# The fields these routes read of a source.
PROJECTION = {'name': 1, 'owner': 1, 'edl': 1, 'drafts_job': 1, 'cues': 1}
# What a listing says of a draft.
DRAFT_PROJECTION = {'name': 1, 'description': 1, 'edl.duration': 1, 'source': 1}
# What a source keeps of a dropped draft (`models.drafts.DroppedDraft`).
KEPT_OF_DROPPED = ('name', 'recipe', 'values', 'spans', 'scores', 'made_at')

# How many recipes one run may ask for.
MAX_RECIPES = 10
# How long a queued or running job may go unheard from before another may
# start: a worker that died mid-run must not leave the source stuck.
STALE_AFTER = timedelta(minutes=30)


class RecipeRequest(BaseModel):
    recipe: str
    values: dict = {}

    model_config = ConfigDict(extra='forbid')


class DraftsRequest(BaseModel):
    """`POST /project/{id}/drafts`."""

    recipes: List[RecipeRequest] = Field(min_length=1, max_length=MAX_RECIPES)

    model_config = ConfigDict(extra='forbid')


class DraftView(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    source: DraftSource


class DraftsView(BaseModel):
    """`GET /project/{id}/drafts`."""

    job: Optional[DraftsJob] = None
    drafts: List[DraftView]


class Queued(BaseModel):
    job: DraftsJob


class DropRequest(BaseModel):
    """`DELETE /project/{id}/drafts`."""

    drafts: List[str] = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra='forbid')


class Dropped(BaseModel):
    dropped: List[str]


class DraftsStore:
    """The project collection, as these routes use it."""

    def _projects(self):
        return Project.get_motor_collection()

    async def find(self, query: dict) -> Optional[dict]:
        return await self._projects().find_one(query, PROJECTION)

    async def has_words(self, project_id) -> bool:
        found = await self._projects().find_one(
            {'_id': project_id, 'words.0': {'$exists': True}}, {'_id': 1}
        )
        return found is not None

    async def claim(self, project_id, job: dict, stale_before: datetime) -> bool:
        """Record `job` unless a run is under way: queued or running, and
        heard from since `stale_before`. One update, so two requests cannot
        both start one."""
        result = await self._projects().update_one(
            {
                '_id': project_id,
                '$or': [
                    {'drafts_job': None},
                    {'drafts_job.state': {'$nin': list(RUNNING)}},
                    {'drafts_job.updated_at': {'$lt': stale_before}},
                ],
            },
            {'$set': {'drafts_job': job}},
        )
        return result.matched_count == 1

    async def set(self, project_id, fields: dict) -> None:
        await self._projects().update_one({'_id': project_id}, {'$set': fields})

    async def drafts_of(self, query: dict) -> List[dict]:
        return (
            await self._projects()
            .find(query, DRAFT_PROJECTION)
            .sort('_id')
            .to_list(2000)
        )

    async def delete(self, query: dict) -> int:
        result = await self._projects().delete_many(query)
        return result.deleted_count

    async def remember(self, project_id, dropped: List[dict]) -> None:
        """Keep `dropped` on the source, after what it already keeps."""
        await self._projects().update_one(
            {'_id': project_id}, {'$push': {'drafts_dropped': {'$each': dropped}}}
        )


def get_drafts_store() -> DraftsStore:
    return DraftsStore()


def kept_of(draft: dict, dropped_at: datetime) -> dict:
    """What the source keeps of `draft` once it is dropped."""
    source = draft.get('source') or {}
    kept = {'id': str(draft['_id']), 'name': draft.get('name')}
    for key in KEPT_OF_DROPPED:
        if key == 'name':
            continue
        kept[key] = source.get(key) if key != 'recipe' else str(source.get(key) or '')
    kept['duration'] = (draft.get('edl') or {}).get('duration')
    kept['dropped_at'] = dropped_at
    return kept


def get_drafts_queue():
    """How a run reaches the worker: Celery's `delay`."""
    return sculptDrafts.delay


async def owned(store: DraftsStore, item_id: str, user) -> dict:
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    project = await store.find({'_id': ObjectId(item_id), **owner_filter(user, OWNER)})
    if project is None:
        raise fresh(NOT_FOUND)
    return project


def _as_utc(moment):
    if isinstance(moment, datetime) and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def job_of(project: dict) -> Optional[DraftsJob]:
    job = project.get('drafts_job')
    if not job:
        return None
    return DraftsJob.model_validate(
        {**job, 'updated_at': _as_utc(job.get('updated_at'))}
    )


def view_of(draft: dict) -> DraftView:
    source = dict(draft.get('source') or {})
    source['made_at'] = _as_utc(source.get('made_at'))
    return DraftView(
        id=str(draft['_id']),
        name=draft.get('name'),
        description=draft.get('description'),
        duration=(draft.get('edl') or {}).get('duration'),
        source=DraftSource.model_validate(source),
    )


draftsAPI = APIRouter()


@draftsAPI.get('/project/{item_id}/drafts', response_model=DraftsView)
async def listDrafts(
    item_id: str,
    user: User = Depends(current_active_user),
    store: DraftsStore = Depends(get_drafts_store),
):
    """# A source's drafts

    `job`, the last run of recipes over this project, or null, and `drafts`,
    each project cut from it: `{id, name, description, duration, source}`,
    `source` saying which recipe made it with which values, the spans it
    took and the scores it was chosen by. Each opens as any project does.
    """
    project = await owned(store, item_id, user)
    drafts = await store.drafts_of(
        {'source.project': str(project['_id']), **owner_filter(user, OWNER)}
    )
    return DraftsView(job=job_of(project), drafts=[view_of(d) for d in drafts])


@draftsAPI.post(
    '/project/{item_id}/drafts',
    status_code=202,
    response_model=Queued,
    responses={
        404: {'description': 'no such project, or no such recipe'},
        409: {'description': 'a run over this project is under way'},
        422: {'description': 'the project has no words to cut by'},
        503: {'description': 'the job was not queued, and why'},
    },
)
async def makeDrafts(
    item_id: str,
    request: DraftsRequest,
    user: User = Depends(current_active_user),
    store: DraftsStore = Depends(get_drafts_store),
    recipes: RecipeStore = Depends(get_recipe_store),
    queue=Depends(get_drafts_queue),
):
    """# Cut a project into drafts

    `{recipes: [{recipe, values}]}`: each a built-in recipe's name or one of
    yours by id, with values for its fields. Queues a run the worker makes:
    the source's timeline is measured, each recipe runs over its words, its
    sound and its motion, and each draft it leaves is a project of yours
    carrying `source`, with a cue on this project per span it took. Answers
    202 with the `job`, which `GET /project/{id}/drafts` follows: `queued`,
    `running`, then `done` with how many were `made`, or `failed` with the
    reason in `error`.

    422 when the project has no words (`no_words`): transcribe it first.
    404 for a recipe that is not one of the built-in ones or yours
    (`unknown_recipe`). 409 while a run over this project is under way
    (`drafts_running`). 503 when the job could not be queued
    (`drafts_not_queued`).
    """
    project = await owned(store, item_id, user)
    if not await store.has_words(project['_id']):
        raise Refusal(
            Code.NO_WORDS,
            'The project has no words to cut by: transcribe its timeline first.',
        )
    for asked in request.recipes:
        await find_recipe(recipes, asked.recipe, user)
    now = datetime.now(timezone.utc)
    job = {
        'state': 'queued',
        'error': None,
        'recipes': [asked.recipe for asked in request.recipes],
        'made': None,
        'notes': [],
        'updated_at': now,
    }
    if not await store.claim(project['_id'], job, stale_before=now - STALE_AFTER):
        raise Refusal(
            Code.DRAFTS_RUNNING,
            'Recipes are already running over this project; wait for them to finish.',
        )
    payload = [asked.model_dump() for asked in request.recipes]
    try:
        await run_in_threadpool(queue, projectId=str(project['_id']), recipes=payload)
    except Exception as exc:  # noqa: BLE001 - the broker is down, or worse
        failed = {
            **job,
            'state': 'failed',
            'error': f'could not be queued: {exc}'[:300],
            'updated_at': datetime.now(timezone.utc),
        }
        await store.set(project['_id'], {'drafts_job': failed})
        raise Refusal(
            Code.DRAFTS_NOT_QUEUED, f'The run could not be queued: {exc}'
        ) from exc
    return Queued(job=DraftsJob.model_validate(job))


@draftsAPI.delete(
    '/project/{item_id}/drafts',
    response_model=Dropped,
    responses={
        422: {'description': 'a project named is not one of this source\'s drafts'}
    },
)
async def dropDrafts(
    item_id: str,
    request: DropRequest,
    user: User = Depends(current_active_user),
    store: DraftsStore = Depends(get_drafts_store),
):
    """# Drop drafts

    `{drafts: [id]}`: the drafts of this project to let go of, each deleted
    with its cue on this project, and each remembered on this project as
    `drafts_dropped` (its provenance and how long it was when it went), so
    the recipes can be measured by what is kept and dropped. Nothing is
    dropped unless every id names one of this project's drafts of yours
    (`not_a_draft`, 422): a project that is not a draft keeps having no
    delete here.
    """
    project = await owned(store, item_id, user)
    ids = []
    for reference in request.drafts:
        if not ObjectId.is_valid(reference):
            raise Refusal(Code.NOT_A_DRAFT, f'{reference!r} is not the id of a draft.')
        ids.append(ObjectId(reference))
    drafts = await store.drafts_of(
        {
            '_id': {'$in': ids},
            'source.project': str(project['_id']),
            **owner_filter(user, OWNER),
        }
    )
    found = {d['_id'] for d in drafts}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise Refusal(
            Code.NOT_A_DRAFT,
            f'{", ".join(missing)}: not a draft of this project, so nothing was dropped.',
        )
    now = datetime.now(timezone.utc)
    await store.remember(project['_id'], [kept_of(d, now) for d in drafts])
    await store.delete({'_id': {'$in': ids}})
    dropped = {str(i) for i in ids}
    cues = [c for c in (project.get('cues') or []) if str(c.get('ref')) not in dropped]
    if len(cues) != len(project.get('cues') or []):
        await store.set(project['_id'], {'cues': cues})
    return Dropped(dropped=[str(i) for i in ids])
