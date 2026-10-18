import re
import unicodedata
from typing import List, Literal, Optional

from beanie import Document, PydanticObjectId
from otto.models import Edl
from pydantic import BaseModel


class Render(Document):
    edl: Edl
    name: Optional[str]
    project: Optional[str]
    project_id: Optional[PydanticObjectId]
    description: Optional[str]
    duration: Optional[float]
    width: Optional[int] = 1920
    height: Optional[int] = 1080
    fps: Optional[float] = 30.0
    # One of the encoding presets in `utils.encoding`: draft, standard, high.
    quality: Optional[str]
    # Never accepted from a client and never used to encode (contract C5):
    # POST /render answers 422 if either is set, and the encoder settings come
    # from `quality`. Kept, with their old types, so that renders stored when
    # clients did send them still load.
    bitrate: Optional[List]
    ffmpeg_params: Optional[List[str]]
    progress: Optional[float]
    # Written by DbLogger throughout the encode and never modelled here, so the
    # API dropped it on the way out: a caller could see progress reach 100 and
    # still have no way to tell a finished render from a failed one. That is
    # the field anything waiting on a render needs.
    status: Optional[str]
    # Why a failed render failed, in a line, for whoever is waiting on it.
    # Before this the reason went to the worker's log and nowhere else, so a
    # failed render said only that it had failed.
    error: Optional[str]
    link: Optional[str]
    username: Optional[str]
    # The output file's name, `<id>.mp4` -- derived from the id alone, so
    # nothing a client sends can reach the filesystem path.
    filename: Optional[str]
    # What a download is called: readable, and sanitised to a safe file name.
    display_name: Optional[str]
    # Where this render was sent, once it has been. `link` records the
    # resulting URL or path; this records which transport produced it, so a
    # link can be interpreted without guessing from its shape.
    destination: Optional[str]

    # class Config:
    #     title = 'Alfred Render'
    #     collection = 'Render'


class RenderUpdate(Render):
    edl: Optional[Edl]
    name: Optional[str]
    project: Optional[str]
    project_id: Optional[PydanticObjectId]
    description: Optional[str]
    duration: Optional[float]
    resolution: Optional[str]
    progress: Optional[float]
    status: Optional[str]
    link: Optional[str]
    filename: Optional[str]
    destination: Optional[str]


RenderState = Literal['queued', 'rendering', 'rendered', 'failed']

# The stored statuses that mean the output file is complete.
FINISHED = ('RENDERED', 'UPLOADED')


def render_state(status, progress) -> str:
    """What a render is doing, from what the worker has stored (contract C2).

    The stored values are left as they were -- `None` until the worker
    finishes, then `RENDERED`, `UPLOADED` or `failed` -- because existing
    clients read them. This is the one place they are interpreted, so a
    client asks for `state` rather than re-deriving it.
    """
    if status == 'failed':
        return 'failed'
    if status in FINISHED:
        return 'rendered'
    if progress is not None and progress > 0:
        return 'rendering'
    return 'queued'


class RenderStatus(BaseModel):
    """`GET /render/{id}/status` (contracts C2 and M1)."""

    id: str
    state: RenderState
    status: Optional[str]
    progress: Optional[float]
    filename: Optional[str]
    destination: Optional[str]
    error: Optional[str]
    # A signed URL for the finished file, which a browser or any HTTP client
    # can fetch without a session until it expires; null until the render has
    # finished and its file is there. Decided by the route, which knows where
    # files are and holds the signing key.
    download_url: Optional[str]

    @classmethod
    def of(cls, render, download_url=None) -> 'RenderStatus':
        progress = render.progress
        if progress is not None:
            progress = min(max(float(progress), 0.0), 100.0)
        return cls(
            id=str(render.id),
            state=render_state(render.status, render.progress),
            status=render.status,
            progress=progress,
            filename=render.filename,
            destination=render.destination,
            error=render.error,
            download_url=download_url,
        )


def output_filename(render_id) -> str:
    """The file a render is written to: its id and nothing else.

    It was built from the project name, the description and a timestamp, all
    of which arrive in the request -- so a project called `../../x` became a
    write to `/x_...mp4` from the worker. The id is the one part of a render
    nothing outside the server chooses.
    """
    return f'{render_id}.mp4'


_OUTPUT_FILENAME = re.compile(r'[0-9a-f]{24}\.mp4')


def is_output_filename(name) -> bool:
    """Whether `name` is one `output_filename` could have produced."""
    return isinstance(name, str) and bool(_OUTPUT_FILENAME.fullmatch(name))


_UNSAFE = re.compile(r'[^A-Za-z0-9._-]+')


def safe_name(text, fallback='render', limit=80) -> str:
    """`text` as a file name that is safe anywhere it might be saved.

    ASCII letters, digits, `.`, `_` and `-` only, with runs of anything else
    collapsed to one `-`, no leading or trailing dots or dashes (no hidden
    files, no `..`), and at most `limit` characters. Used for the name a
    download is saved under, which a browser writes to the user's disk.
    """
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = _UNSAFE.sub('-', text).strip('-._')
    text = text[:limit].rstrip('-._')
    return text or fallback


def display_name_for(render) -> str:
    """A readable name for `render`'s output: project, description and size."""
    parts = [render.project or render.name, render.description]
    if render.width and render.height:
        parts.append(f'{render.width}x{render.height}')
    return safe_name('-'.join(str(part) for part in parts if part))
