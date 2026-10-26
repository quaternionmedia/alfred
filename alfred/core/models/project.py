from typing import List, Optional

from beanie import Document
from otto.models import Edl
from pydantic import BaseModel, ConfigDict, field_serializer
from pymongo import ASCENDING, IndexModel

from .captions import Caption, CaptionsJob, CaptionStyle

# At most one generated demo per account, held by MongoDB rather than by the
# route. `POST /demo/project` is find-or-insert, and two requests for the same
# account could both find nothing and both insert; with this index the second
# insert fails and the route answers with the first one's project. Partial, so
# it constrains the generated demo and no other project -- an account may have
# as many projects called "Demo" as it likes.
#
# Built at startup by `routes.demo`, not declared in Settings for beanie to
# build: see `keepOneDemoPerOwner` for why.
ONE_DEMO_PER_OWNER = IndexModel(
    [('owner', ASCENDING)],
    name='one_demo_per_owner',
    unique=True,
    partialFilterExpression={'demo': True},
)


def as_sent(edl: Edl) -> dict:
    """An EDL as its sender wrote it: the fields they set, and only those.

    Validated against otto's models on the way in, which fill in what was not
    sent -- every clip gains `fadeIn: 1`, `fadeOut: 1`, `duration: 5`,
    `relative: true` and a null for each other field. Stored like that, a
    saved timeline said more than the editor did: a clip nobody gave a fade
    came back carrying a one-second one, indistinguishable from a chosen fade,
    and rendered with it. So a project keeps exactly what it was sent (contract
    M4), and the engine applies its own defaults when it renders. Clips stored
    before this keep the defaults written into them.

    Anything a model does not declare -- the editor's view index `i` on each
    clip -- is gone either way: validation drops it.
    """
    return edl.model_dump(exclude_unset=True)


class RenderSettings(BaseModel):
    """What a project renders at, when nobody says otherwise.

    Separate from `Render` deliberately. A Render is one job with a result;
    this is the project's standing preference, and conflating them would mean
    a project could not describe how it should be rendered until it had been
    rendered once.
    """

    width: Optional[int] = 1920
    height: Optional[int] = 1080
    fps: Optional[float] = 30.0
    quality: Optional[str] = None


class Project(Document):
    logic: dict
    fields: Optional[List] = None
    name: Optional[str] = None
    # Whose project this is: the owner key of the account that created it --
    # its email, today -- the same identity a render records in `username`.
    # `utils.ownership` decides both, and docs/ownership.md is why the email
    # is a key on its way out.
    #
    # Set by the server on every path that creates a project, and never taken
    # from a request -- a body that names an owner has it replaced on create
    # and ignored on update. Non-superusers see and act on only their own
    # projects; superusers see all of them.
    #
    # Optional because every project stored before this field existed has
    # none. Those are readable and writable by superusers only: nobody can be
    # shown to own them, and guessing would hand one account another's work.
    owner: Optional[str] = None
    # The timeline editor has always read `project.edl` -- OttoTimeline's
    # oninit does `Edl.edl = e.edl` -- and the model has never had the field,
    # so the value was always undefined and the timeline always empty. There
    # was nothing to fix in the editor; it was asking for something the API
    # could not return.
    #
    # Optional, so every existing project stays valid: a project built for the
    # form-driven flow has logic and fields and no timeline, which is still a
    # legitimate project. `Render` already models its edl with otto's type, so
    # this follows what the render side established rather than inventing a
    # second shape for the same document.
    edl: Optional[Edl] = None
    # What the render and deliver stages should default to for this project.
    #
    # This is what makes the flow reusable rather than a wizard re-run from
    # scratch: reopening a project brings back the size it renders at and where
    # its output goes, so "the weekly promo" is a thing you pick, not a set of
    # fields you retype. Both optional -- a project that has never been
    # rendered has no opinion yet, and the stages fall back to their own
    # defaults.
    render_settings: Optional[RenderSettings] = None
    destination: Optional[str] = None
    # True on the project `POST /demo/project` generated for its owner, and on
    # no other. Server-owned like `owner`: dropped from a create, kept as stored
    # on an update, so no request can mark a project or unmark the demo -- the
    # index above counts on it.
    demo: Optional[bool] = None
    # The project's captions, in timeline seconds, and how they are drawn
    # (contract K2; `models.captions`). Written through
    # `PUT /project/{id}/captions`, which checks them as a list, and by a
    # transcription; a whole-project update keeps them as stored.
    captions: Optional[List[Caption]] = None
    caption_style: Optional[CaptionStyle] = None
    # The last transcription of the timeline's sound. The server's record,
    # like `owner`: no request writes it.
    captions_job: Optional[CaptionsJob] = None

    model_config = ConfigDict(title='Alfred Project')

    class Settings:
        # Every write of a project -- create, update, save, set -- stores its
        # EDL as sent: beanie encodes a document's fields through these.
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
