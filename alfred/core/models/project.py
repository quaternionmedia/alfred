from typing import List, Optional

from beanie import Document
from otto.models import Edl
from pydantic import BaseModel


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
    quality: Optional[str]


class Project(Document):
    logic: dict
    fields: Optional[List]
    name: Optional[str]
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
    edl: Optional[Edl]
    # What the render and deliver stages should default to for this project.
    #
    # This is what makes the flow reusable rather than a wizard re-run from
    # scratch: reopening a project brings back the size it renders at and where
    # its output goes, so "the weekly promo" is a thing you pick, not a set of
    # fields you retype. Both optional -- a project that has never been
    # rendered has no opinion yet, and the stages fall back to their own
    # defaults.
    render_settings: Optional[RenderSettings]
    destination: Optional[str]

    class Config:
        title = 'Alfred Project'


class ProjectUpdate(Project):
    logic: Optional[dict]
    fields: Optional[List]
    edl: Optional[Edl]
    render_settings: Optional[RenderSettings]
    destination: Optional[str]
