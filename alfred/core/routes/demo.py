"""Generate a demo, so an empty install has something to edit.

otto synthesises the clips from ffmpeg's test sources (`otto.demo`): no
network, unlike `./al demo`, whose bucket fetch the adoption record lists as
an open gap. alfred runs no ffmpeg of its own.
"""

import os
from os import makedirs
from os.path import getsize, isfile, join
from threading import Lock
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from otto.demo import DEMO_DURATION, demoClip
from otto.exceptions import FFmpegException
from pydantic import BaseModel
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure

from alfred.config import VIDEO_DIR

from ..utils.db import User, get_db
from ..utils.ownership import owner_key
from .users import current_active_user

demoAPI = APIRouter()


@demoAPI.on_event('startup')
async def keepOneDemoPerOwner():
    """Build the index that keeps one demo per account under concurrency.

    By hand, not declared for beanie: over existing duplicates (`./al reseed`
    drops the index) a declared one stops the api starting. A failed build is
    reported with the accounts to tidy, and the api starts without it. Runs
    before beanie is initialised, so the collection is reached by name.
    """
    from ..models.project import ONE_DEMO_PER_OWNER, Project

    collection = get_db()[Project.__name__]
    try:
        await collection.create_indexes([ONE_DEMO_PER_OWNER])
    except OperationFailure as exc:
        doubled = await collection.aggregate(
            [
                {'$match': {'demo': True}},
                {'$group': {'_id': '$owner', 'demos': {'$sum': 1}}},
                {'$match': {'demos': {'$gt': 1}}},
            ]
        ).to_list(20)
        line = '!' * 72
        print(line, flush=True)
        print(
            '  ONE DEMO PER ACCOUNT IS NOT ENFORCED: the index did not build.',
            flush=True,
        )
        print(f'  {exc}', flush=True)
        for row in doubled:
            print(f'  {row["_id"]} has {row["demos"]} demo projects', flush=True)
        print('  Delete the extra ones and restart to build it.', flush=True)
        print(line, flush=True)


# Each file, and its picture by otto's name: 3 s at 320x180, a second to make.
DEMO_CLIPS = (
    ('demo-bars.mp4', 'bars'),
    ('demo-testcard.mp4', 'testcard'),
    ('demo-colour.mp4', 'color'),
)

DEMO_PROJECT_NAME = 'Demo'


class GeneratedMedia(BaseModel):
    created: list[str]
    skipped: list[str]


def partial_path(path):
    """Where `path` is written until it is whole: beside it, under a hidden
    name, which the library never lists (`utils.media.is_library_filename`)."""
    directory, name = os.path.split(path)
    return join(directory, f'.{name}.{uuid4().hex}.part')


def generate_clip(path, source, duration=DEMO_DURATION):
    """Have the engine synthesise one clip. Returns nothing; raises on failure.

    `source` is otto's name for the picture (`otto.demo.DEMO_SOURCES`).
    Written under `partial_path`, then moved into place, so no listing offers
    a half-written clip.
    """
    partial = partial_path(path)
    try:
        try:
            demoClip(partial, source, duration=duration)
        except FFmpegException as exc:
            raise HTTPException(
                status_code=500,
                detail=f'ffmpeg could not generate {path}: {exc.stderr[-400:]}',
            ) from exc
        except OSError as exc:
            # The engine could not start its ffmpeg at all.
            raise HTTPException(
                status_code=503,
                detail=f'no ffmpeg available to generate demo media: {exc}',
            ) from exc
        os.replace(partial, path)
    except BaseException:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise


# One generation at a time: a second press waits, then finds the clips made.
_generating = Lock()


# A plain function, so each clip's ffmpeg run is off the event loop.
@demoAPI.post('/demo/media', response_model=GeneratedMedia)
def generateDemoMedia():
    """# Generate demo media

    Has the engine synthesise a few short clips locally, so an empty install
    has something to edit without downloading anything.

    Existing files are left alone and reported as skipped, so pressing the
    button twice is not a way to lose work you have already put on a timeline.
    """
    makedirs(VIDEO_DIR, exist_ok=True)

    created, skipped = [], []
    with _generating:
        for name, source in DEMO_CLIPS:
            path = join(VIDEO_DIR, name)
            if isfile(path) and getsize(path) > 0:
                skipped.append(name)
                continue
            generate_clip(path, source)
            created.append(name)

    return GeneratedMedia(created=created, skipped=skipped)


class DemoProject(BaseModel):
    id: str
    name: str
    clips: int
    created: bool


@demoAPI.post('/demo/project', response_model=DemoProject)
async def generateDemoProject(user: User = Depends(current_active_user)):
    """# Generate a demo project

    Creates a project with a timeline already on it, so the editor opens onto
    something rather than onto an explanation of what it would show if you had
    any.

    Template clips only, which need no media on disk. One per account:
    asking again returns the one you have, renamed or not.
    """
    from ..models import Project

    # One find-or-insert; the partial unique index (models/project.py) refuses
    # a racing second insert. An unmarked project called "Demo" counts too.
    collection = Project.get_motor_collection()
    owner = owner_key(user)
    yours = {'owner': owner, '$or': [{'demo': True}, {'name': DEMO_PROJECT_NAME}]}
    # Chosen here, to tell whether this request inserted.
    new_id = ObjectId()
    try:
        demo = await collection.find_one_and_update(
            yours,
            {'$setOnInsert': {'_id': new_id, **_demo_project_document(owner)}},
            upsert=True,
            # The marked demo first, if an account has both kinds.
            sort=[('demo', DESCENDING)],
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        # A racing request inserted first; theirs is the demo.
        demo = await collection.find_one({'owner': owner, 'demo': True})
    if demo is None:
        # Inserted and deleted again before this read.
        raise HTTPException(
            status_code=409, detail='The demo project changed meanwhile; ask again'
        )
    return DemoProject(
        id=str(demo['_id']),
        name=demo.get('name') or DEMO_PROJECT_NAME,
        clips=len((demo.get('edl') or {}).get('clips') or []),
        created=demo['_id'] == new_id,
    )


def _demo_project_document(owner):
    # Amber text, drawn on black.
    return dict(
        name=DEMO_PROJECT_NAME,
        owner=owner,
        demo=True,
        logic={},
        fields=[],
        edl={
            'clips': [
                {
                    'type': 'template',
                    'name': 'title',
                    'duration': 3.0,
                    'start': 0.0,
                    'data': {'text': 'Alfred', 'color': '#f2aa4c'},
                },
                {
                    'type': 'template',
                    'name': 'textBox',
                    'duration': 4.0,
                    'start': 3.0,
                    'data': {
                        'text': 'Drama is life with the dull bits cut out.',
                        'color': '#f2aa4c',
                    },
                },
                {
                    'type': 'template',
                    'name': 'makeColor',
                    'duration': 2.0,
                    'start': 7.0,
                    'data': {'color': '#f2aa4c'},
                },
            ],
            'duration': 9.0,
        },
    )
