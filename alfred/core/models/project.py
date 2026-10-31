from typing import List, Optional

from beanie import Document
from otto.models import Edl
from pydantic import BaseModel, ConfigDict, field_serializer
from pymongo import ASCENDING, IndexModel

from .captions import Caption, CaptionsJob, CaptionStyle

# One generated demo per account, held by MongoDB: two racing
# `POST /demo/project`s cannot both insert. Partial: only `demo: true` counts.
# Built at startup by `routes.demo` (`keepOneDemoPerOwner` says why).
ONE_DEMO_PER_OWNER = IndexModel(
    [('owner', ASCENDING)],
    name='one_demo_per_owner',
    unique=True,
    partialFilterExpression={'demo': True},
)


def as_sent(edl: Edl) -> dict:
    """An EDL as its sender wrote it: the fields they set, and only those.

    otto's models fill in defaults (`fadeIn: 1`, `duration: 5`, ...), which
    stored would read as choices; a project keeps what it was sent (contract
    M4), and otto applies its defaults at render. Undeclared fields, such as
    the editor's `i`, are dropped by validation.
    """
    return edl.model_dump(exclude_unset=True)


class RenderSettings(BaseModel):
    """What a project renders at, when nobody says otherwise: a standing
    preference, not a `Render`, which is one job with a result."""

    width: Optional[int] = 1920
    height: Optional[int] = 1080
    fps: Optional[float] = 30.0
    quality: Optional[str] = None


class Project(Document):
    logic: dict
    fields: Optional[List] = None
    name: Optional[str] = None
    # The creator's owner key (`utils.ownership`, docs/ownership.md). Set by
    # the server, never from a request. None: superusers only.
    owner: Optional[str] = None
    # The timeline. None for a form-flow project, which has logic and fields.
    edl: Optional[Edl] = None
    # What the render and deliver stages default to; None until chosen.
    render_settings: Optional[RenderSettings] = None
    destination: Optional[str] = None
    # True on the generated demo alone. Server-owned, as the index needs.
    demo: Optional[bool] = None
    # In timeline seconds (K2). Written by `PUT /project/{id}/captions` and a
    # transcription; a whole-project update keeps them.
    captions: Optional[List[Caption]] = None
    caption_style: Optional[CaptionStyle] = None
    # The last transcription. Server-owned.
    captions_job: Optional[CaptionsJob] = None

    model_config = ConfigDict(title='Alfred Project')

    class Settings:
        # Every write stores the EDL as sent.
        bson_encoders = {Edl: as_sent}

    @field_serializer('edl')
    def _edl_as_stored(self, edl, info):
        """The EDL as stored, not as otto fills it in: every dump and answer (M4)."""
        if edl is None:
            return None
        return edl.model_dump(
            mode=info.mode,
            exclude_unset=True,
            by_alias=bool(info.by_alias),
            exclude_none=info.exclude_none,
        )


class ProjectUpdate(Project):
    logic: Optional[dict] = None
    fields: Optional[List] = None
    edl: Optional[Edl] = None
    render_settings: Optional[RenderSettings] = None
    destination: Optional[str] = None
