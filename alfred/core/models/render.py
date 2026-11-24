import re
import unicodedata
from typing import List, Literal, Optional

from beanie import Document, PydanticObjectId
from otto.models import Edl
from pydantic import BaseModel

from .captions import Caption, CaptionStyle


class Render(Document):
    edl: Edl
    name: Optional[str] = None
    project: Optional[str] = None
    project_id: Optional[PydanticObjectId] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = 1920
    height: Optional[int] = 1080
    fps: Optional[float] = 30.0
    # One of the encoding presets in `utils.encoding`: draft, standard, high.
    quality: Optional[str] = None
    # Refused on POST /render and never used (C5); kept so old renders load.
    bitrate: Optional[List] = None
    ffmpeg_params: Optional[List[str]] = None
    progress: Optional[float] = None
    # The worker's own value (DbLogger); `render_state` reads it.
    status: Optional[str] = None
    # Why a failed render failed, in a line.
    error: Optional[str] = None
    link: Optional[str] = None
    username: Optional[str] = None
    # `<id>.mp4`: nothing a client sends reaches the path.
    filename: Optional[str] = None
    # What a download is called: readable, and sanitised to a safe file name.
    display_name: Optional[str] = None
    # The destination `link` came from, so a link is read without guessing.
    destination: Optional[str] = None
    # Drawn over the timeline at each queueing, not written into `edl` (K2).
    # None, or a style with `enabled: false`, draws none.
    captions: Optional[List[Caption]] = None
    caption_style: Optional[CaptionStyle] = None


class RenderUpdate(Render):
    edl: Optional[Edl] = None
    name: Optional[str] = None
    project: Optional[str] = None
    project_id: Optional[PydanticObjectId] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    resolution: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None
    link: Optional[str] = None
    filename: Optional[str] = None
    destination: Optional[str] = None


RenderState = Literal['queued', 'rendering', 'rendered', 'failed']

# The stored statuses that mean the output file is complete.
FINISHED = ('RENDERED', 'UPLOADED')


def render_state(status, progress) -> str:
    """What a render is doing, from what the worker stored (contract C2).

    The one reading of `status` (None, then `RENDERED`, `UPLOADED` or
    `failed`), which clients still get raw beside `state`.
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
    status: Optional[str] = None
    progress: Optional[float] = None
    filename: Optional[str] = None
    destination: Optional[str] = None
    error: Optional[str] = None
    # Signed, fetchable without a session until it expires; null until the
    # file is there. Set by the route.
    download_url: Optional[str] = None

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
    """The file a render is written to: its id, which no client chooses."""
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
