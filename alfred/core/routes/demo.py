"""Generate a demo, rather than telling people they have none.

The Source stage used to answer an empty install with "No projects yet." and
"No media on the server. `./al demo` downloads some." Both are accurate and
neither is useful: the first is a dead end, and the second sends you to a shell
to download four files over the network before the editor will show you
anything.

Everything here is synthesised on the spot by the engine, from ffmpeg's own
test sources -- colour bars, a test card, a plain colour (`otto.demo`). No
network, no downloads, no CDN. That matters beyond convenience: `./al demo`
fetches from a Google Cloud Storage bucket, and the adoption record lists
third-party fetches as an open governance gap, so a first-run experience that
needs one is a gap anybody evaluating this project walks straight into.

The engine already carries ffmpeg -- it is how renders are encoded -- so this
adds no dependency, and alfred runs no ffmpeg of its own.
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

    By hand rather than declared on the model. beanie builds declared indexes
    inside `init_beanie`, and a unique index cannot be built over duplicates
    -- which a database can hold if the index went missing under a running
    server, as `./al reseed` drops it with the collection -- so a declared one
    would stop the API starting at all. Here a failed build is reported, with
    the accounts to tidy, and the API starts without it: the route still
    answers correctly, and only two simultaneous first requests could again
    make two demos.

    Before beanie is initialised (the router's hooks run first), so the
    collection is reached by name: beanie names it after the class.
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


# Small, short and synthetic. The point is to have something real to edit, not
# to be representative footage -- the engine's demo clips are 3 seconds at
# 320x180, which encode in about a second and cost a few kilobytes on disk.
# Each file is named here, and its picture by the engine's name for it.
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

    `source` is the engine's name for the picture (`otto.demo.DEMO_SOURCES`).
    Written under `partial_path` and moved into place once the engine has
    finished. Other requests are answered while it runs, and a listing taken
    meanwhile must not offer a clip that is half written.
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


# One generation at a time, in this process. Two presses of the button at
# once would each find the clips missing and both have ffmpeg write the same
# files; held here, the second waits for the first, finds its clips, and says
# they were skipped.
_generating = Lock()


# A plain function, not a coroutine: FastAPI runs it in its thread pool. Each
# clip is an ffmpeg run of about a second, in the engine, and as a coroutine
# every one of them ran on the event loop, so the api answered nothing else --
# `/healthz` included -- until the last clip was written.
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

    Template clips only. A project referring to media files would break the
    moment those files were cleaned up, and templates render from nothing on
    disk -- so this works on an install that has never generated media and
    never will.

    The project belongs to whoever asked, and is idempotent per account:
    asking twice returns the one you already have rather than accumulating one
    per click -- renamed or not. It was idempotent by name across the whole
    server, which under ownership would have handed the second person to ask
    somebody else's demo -- or, filtered properly, a demo they could not open.
    """
    from ..models import Project

    # One find-or-insert, so the decision is MongoDB's rather than a
    # check-then-create that two presses of the button could both pass. The
    # upsert alone was not enough either: two requests could both match
    # nothing and both insert, and the e2e suite, which presses it from
    # several workers at once, ended up with two demos. The partial unique
    # index on `{owner}` where `demo` (models/project.py) refuses the second
    # insert, and the request that loses answers with the winner's project.
    #
    # The demo is the project marked `demo`. One called "Demo" without the
    # mark is an account's demo from before the mark existed, or one it named
    # itself, and is returned as before rather than joined by a second.
    collection = Project.get_motor_collection()
    owner = owner_key(user)
    yours = {'owner': owner, '$or': [{'demo': True}, {'name': DEMO_PROJECT_NAME}]}
    # Chosen here, so the answer says whether this request is the one that
    # inserted: the document comes back either way.
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
        # Another request for this account inserted between this one's match
        # and its insert, and the index refused this one. Theirs is the demo.
        demo = await collection.find_one({'owner': owner, 'demo': True})
    if demo is None:
        # Inserted by the winner and deleted again before this read: too
        # fast to say anything but "again".
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
    # The text is drawn straight onto the frame, which is black: in the
    # editor's amber it shows. It was the editor's near-black, #101820, which
    # on black is all but invisible.
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
