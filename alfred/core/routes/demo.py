"""Generate a demo, rather than telling people they have none.

The Source stage used to answer an empty install with "No projects yet." and
"No media on the server. `./al demo` downloads some." Both are accurate and
neither is useful: the first is a dead end, and the second sends you to a shell
to download four files over the network before the editor will show you
anything.

Everything here is synthesised on the spot with ffmpeg's own test sources --
`testsrc`, `smptebars`, `color`. No network, no downloads, no CDN. That matters
beyond convenience: `./al demo` fetches from a Google Cloud Storage bucket, and
the adoption record lists third-party fetches as an open governance gap, so a
first-run experience that needs one is a gap anybody evaluating this project
walks straight into.

ffmpeg is already present -- it is how renders are encoded -- so this adds no
dependency.
"""

import subprocess
from os import makedirs
from os.path import getsize, isfile, join

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alfred.config import VIDEO_DIR

from ..utils.db import User
from .users import current_active_user

demoAPI = APIRouter()


# Small, short and synthetic. The point is to have something real to edit, not
# to be representative footage -- a 3-second 320x180 clip encodes in about a
# second and costs a few kilobytes on disk.
DEMO_CLIPS = (
    ('demo-bars.mp4', 'smptebars=size=320x180:rate=24'),
    ('demo-testcard.mp4', 'testsrc=size=320x180:rate=24'),
    ('demo-colour.mp4', 'color=c=0x101820:size=320x180:rate=24'),
)
DEMO_DURATION = 3

DEMO_PROJECT_NAME = 'Demo'


class GeneratedMedia(BaseModel):
    created: list[str]
    skipped: list[str]


def ffmpeg_binary():
    """The same ffmpeg moviepy encodes with.

    Resolved through imageio_ffmpeg rather than PATH, because that is what the
    render path uses and there is no ffmpeg on PATH in these images. Probing
    PATH here would report ffmpeg missing on a machine that renders video
    perfectly well.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001 - any failure here means no ffmpeg
        raise HTTPException(
            status_code=503,
            detail=f'no ffmpeg available to generate demo media: {exc}',
        ) from exc


def generate_clip(path, source, duration=DEMO_DURATION):
    """Synthesise one clip. Returns nothing; raises on failure."""
    result = subprocess.run(
        [
            ffmpeg_binary(),
            '-nostdin',
            '-y',
            '-f',
            'lavfi',
            '-i',
            f'{source}:duration={duration}',
            # yuv420p so the result plays in a browser. ffmpeg's test sources
            # default to a pixel format most players will not touch, which
            # would make demo media that exists and cannot be previewed --
            # worse than none.
            '-pix_fmt',
            'yuv420p',
            path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not isfile(path):
        raise HTTPException(
            status_code=500,
            detail=f'ffmpeg could not generate {path}: {result.stderr[-400:]}',
        )


@demoAPI.post('/demo/media', response_model=GeneratedMedia)
async def generateDemoMedia():
    """# Generate demo media

    Synthesises a few short clips locally with ffmpeg, so an empty install has
    something to edit without downloading anything.

    Existing files are left alone and reported as skipped, so pressing the
    button twice is not a way to lose work you have already put on a timeline.
    """
    makedirs(VIDEO_DIR, exist_ok=True)

    created, skipped = [], []
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
    per click. It was idempotent by name across the whole server, which under
    ownership would have handed the second person to ask somebody else's demo
    -- or, filtered properly, a demo they could not open.
    """
    from ..models import Project

    # Check-then-create is not atomic, and this endpoint is one button that
    # people press twice. Two concurrent requests both found nothing and both
    # inserted, so "idempotent by name" held only when nobody raced it -- the
    # e2e suite raced it immediately and ended up with two projects called
    # Demo. An upsert with $setOnInsert leaves the decision to MongoDB.
    collection = Project.get_motor_collection()
    mine = {'name': DEMO_PROJECT_NAME, 'owner': user.email}
    # The document *before* the update, so None means this call is the one that
    # created it. Asking for the document after would return one either way and
    # make `created` permanently false.
    previous = await collection.find_one_and_update(
        mine,
        {'$setOnInsert': _demo_project_document(owner=user.email)},
        upsert=True,
        return_document=False,
    )

    stored = await Project.find_one(mine)
    clips = len(stored.edl.clips) if stored and stored.edl else 0
    return DemoProject(
        id=str(stored.id),
        name=stored.name,
        clips=clips,
        created=previous is None,
    )


def _demo_project_document(owner):
    return dict(
        name=DEMO_PROJECT_NAME,
        owner=owner,
        logic={},
        fields=[],
        edl={
            'clips': [
                {
                    'type': 'template',
                    'name': 'title',
                    'duration': 3.0,
                    'start': 0.0,
                    'data': {'text': 'Alfred', 'color': '#101820'},
                },
                {
                    'type': 'template',
                    'name': 'textBox',
                    'duration': 4.0,
                    'start': 3.0,
                    'data': {
                        'text': 'Drama is life with the dull bits cut out.',
                        'color': '#101820',
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
