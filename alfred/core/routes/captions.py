"""Captions on a project (contract K2): read them, write them, import them
from a subtitle file, and have the timeline's sound transcribed into them.

Every route is scoped to the caller the way every project route is
(`utils.ownership`): a project that is not yours answers 404, exactly as one
that does not exist. The routes reach MongoDB only through `CaptionsStore`
and Celery only through `get_captions_queue`, so a test can stand in for
either.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from otto.models import Edl
from pydantic import BaseModel, ValidationError, constr

from alfred import config

from ..models.captions import RUNNING, Caption, CaptionsJob, CaptionStyle
from ..models.project import Project
from ..utils import audio_engine
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.captions import (
    CaptionFormatError,
    TooManyCaptions,
    checked_captions,
    parse,
    project_style,
    style_to_store,
)
from ..utils.db import User
from ..utils.media import RefusedEdl, check_edl
from ..utils.ownership import owner_filter
from ..utils.tasks import transcribeCaptions
from ..utils.transcription import sounding_timeline
from .templates import TEMPLATE_NAMES
from .users import current_active_user

# Where a project keeps its owner key; see routes.project.
OWNER = 'owner'

# The largest subtitle file an import reads, in characters: a feature film's
# SubRip is a few hundred kilobytes.
MAX_IMPORT_CHARS = 2_000_000

# The fields these routes read.
PROJECTION = {'edl': 1, 'captions': 1, 'caption_style': 1, 'captions_job': 1}


def stale_after() -> timedelta:
    """How long a queued or running transcription may go unheard from before
    another may start in its place: a worker that died mid-job must not leave
    the project unable to be transcribed again. The engine's timeout, which
    bounds the longest wait on it, and a quarter of an hour for mixing the
    timeline. A job left queued behind long renders for longer than that may
    be joined by a second; both finish, and the later one's captions stand."""
    return timedelta(seconds=config.AUDIO_ENGINE_TIMEOUT + 900)


class CaptionsView(BaseModel):
    """`GET /project/{id}/captions`."""

    captions: List[Caption]
    style: CaptionStyle
    job: Optional[CaptionsJob]


class CaptionsUpdate(BaseModel):
    """`PUT /project/{id}/captions`: the captions, and -- if sent -- the style."""

    captions: List[Caption]
    style: Optional[CaptionStyle]

    class Config:
        extra = 'forbid'


class CaptionsImport(BaseModel):
    format: Literal['srt', 'vtt', 'json']
    text: constr(max_length=MAX_IMPORT_CHARS)


class ImportedCaptions(BaseModel):
    """What a subtitle file holds, for the editor to review before it saves."""

    captions: List[Caption]
    # Cues left out for having no text or no length.
    skipped: int


class Transcribing(BaseModel):
    job: CaptionsJob


class CaptionsStore:
    """The project collection, as these routes use it."""

    def _projects(self):
        return Project.get_motor_collection()

    async def find(self, query: dict) -> Optional[dict]:
        return await self._projects().find_one(query, PROJECTION)

    async def set(self, project_id, fields: dict) -> None:
        await self._projects().update_one({'_id': project_id}, {'$set': fields})

    async def claim(self, project_id, job: dict, stale_before: datetime) -> bool:
        """Record `job` unless a transcription is already under way: one that
        is queued or running and has been heard from since `stale_before`.
        One update, so two requests cannot both start one."""
        result = await self._projects().update_one(
            {
                '_id': project_id,
                '$or': [
                    {'captions_job.state': {'$nin': list(RUNNING)}},
                    {'captions_job.updated_at': {'$lt': stale_before}},
                ],
            },
            {'$set': {'captions_job': job}},
        )
        return result.matched_count == 1


def get_captions_store() -> CaptionsStore:
    return CaptionsStore()


def get_captions_queue():
    """How a transcription reaches the worker: Celery's `delay`."""
    return transcribeCaptions.delay


async def owned(store: CaptionsStore, item_id: str, user) -> dict:
    """The project `item_id` if `user` may reach it: 422 for a malformed id,
    404 for one that is not theirs or not there."""
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


def view_of(project: dict) -> CaptionsView:
    """A stored project's captions, style and job, as the routes answer."""
    captions = []
    for stored in project.get('captions') or []:
        try:
            captions.append(Caption.parse_obj(stored))
        except ValidationError as exc:
            # Stored by something that skipped the checks; shown without it
            # rather than failing the whole read.
            print('skipping a stored caption that does not validate:', exc)
    style = project_style(project.get('caption_style'))
    job = project.get('captions_job')
    if job:
        job = CaptionsJob.parse_obj(
            {**job, 'updated_at': _as_utc(job.get('updated_at'))}
        )
    return CaptionsView(captions=captions, style=style, job=job or None)


captionsAPI = APIRouter()


@captionsAPI.get('/project/{item_id}/captions', response_model=CaptionsView)
async def getProjectCaptions(
    item_id: str,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
):
    """# A project's captions

    `captions`, each `{start, end, text}` in timeline seconds and in order;
    `style`, how they are drawn -- `enabled` says whether they are drawn into
    the project's renders at all, false until someone says so; every other
    field is optional, defaults applied when they are rendered -- and `job`,
    the last transcription of the timeline's sound, or null.
    """
    return view_of(await owned(store, item_id, user))


@captionsAPI.put('/project/{item_id}/captions', response_model=CaptionsView)
async def saveProjectCaptions(
    item_id: str,
    update: CaptionsUpdate,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
):
    """# Save a project's captions

    Replaces the captions with `captions`, and the style with `style` when
    one is sent; nothing else on the project is written. Each caption starts
    at or after 0, ends after it starts and has text, at most 500 characters
    of it; they are stored in order of when they start, at most 1000.

    The style's `enabled` is always stored: as sent, else as it was, else
    false -- a project's captions are not drawn into its renders until
    someone says they should be. Answers `{captions, style, job}` as stored.
    """
    project = await owned(store, item_id, user)
    try:
        captions = checked_captions(update.captions)
    except TooManyCaptions as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fields = {'captions': [caption.dict() for caption in captions]}
    style = style_to_store(update.style, project.get('caption_style'))
    if style is not None:
        fields['caption_style'] = style
    await store.set(project['_id'], fields)
    return view_of({**project, **fields})


@captionsAPI.post('/project/{item_id}/captions/import', response_model=ImportedCaptions)
async def importProjectCaptions(
    item_id: str,
    upload: CaptionsImport,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
):
    """# Read captions from a subtitle file

    `format` is `srt`, `vtt` or `json`; `text` is the file's content. Answers
    the captions it holds, in order -- and stores nothing: the editor shows
    them for review, then saves with `PUT /project/{id}/captions`. `skipped`
    counts cues left out for having no text or no length. 422, naming the
    line, for a file that cannot be read.
    """
    await owned(store, item_id, user)
    try:
        parsed = parse(upload.format, upload.text)
    except CaptionFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImportedCaptions(captions=parsed.captions, skipped=parsed.skipped)


def timeline_to_transcribe(project: dict) -> Edl:
    """The project's saved timeline, if there is something in it to hear;
    422 saying why not otherwise."""
    stored = project.get('edl') or {}
    if not stored.get('clips'):
        raise HTTPException(
            status_code=422,
            detail='The project has no saved timeline to transcribe; save one first.',
        )
    try:
        edl = Edl.parse_obj(stored)
        check_edl(edl, TEMPLATE_NAMES)
    except (ValidationError, RefusedEdl) as exc:
        raise HTTPException(
            status_code=422, detail=f'The saved timeline cannot be played: {exc}'
        ) from exc
    if sounding_timeline(edl) is None:
        raise HTTPException(
            status_code=422,
            detail=(
                'The timeline has no video or audio clips, so there is nothing '
                'to transcribe.'
            ),
        )
    return edl


@captionsAPI.post(
    '/project/{item_id}/captions/transcribe',
    status_code=202,
    response_model=Transcribing,
    responses={
        409: {'description': 'a transcription of this project is under way'},
        422: {'description': 'nothing in the saved timeline to transcribe'},
        503: {'description': 'no audio engine to transcribe with, and why'},
    },
)
async def transcribeProjectCaptions(
    item_id: str,
    user: User = Depends(current_active_user),
    store: CaptionsStore = Depends(get_captions_store),
    queue=Depends(get_captions_queue),
):
    """# Transcribe the timeline into captions

    Queues the project's saved timeline to be heard by the audio engine: the
    worker mixes its sound, the engine transcribes it, and what it said
    replaces the project's captions. Answers 202 with the `job`, which
    `GET /project/{id}/captions` follows: `queued`, `transcribing`, then
    `done` -- with how many `segments` were heard -- or `failed`, with the
    reason in `error`.

    503, saying why, when there is no audio engine to ask; 409 while a
    transcription of this project is under way; 422 when the saved timeline
    has nothing to hear.
    """
    project = await owned(store, item_id, user)
    reason = audio_engine.problem()
    if reason:
        raise HTTPException(status_code=503, detail=reason)
    timeline_to_transcribe(project)

    now = datetime.now(timezone.utc)
    job = {
        'state': 'queued',
        'error': None,
        'engine': audio_engine.describe(),
        'segments': None,
        'updated_at': now,
    }
    if not await store.claim(project['_id'], job, stale_before=now - stale_after()):
        raise HTTPException(
            status_code=409,
            detail=(
                "This project's timeline is already being transcribed; wait for "
                'that to finish.'
            ),
        )
    try:
        queue(projectId=str(project['_id']))
    except Exception as exc:  # noqa: BLE001 - the broker is down, or worse
        failed = {
            **job,
            'state': 'failed',
            'error': f'could not be queued: {exc}'[:300],
            'updated_at': datetime.now(timezone.utc),
        }
        await store.set(project['_id'], {'captions_job': failed})
        raise HTTPException(
            status_code=503, detail=f'The transcription could not be queued: {exc}'
        ) from exc
    return Transcribing(job=CaptionsJob.parse_obj(job))
