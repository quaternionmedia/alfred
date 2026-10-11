from typing import Optional, List
from beanie import Document
from otto.models import Edl


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

    class Config:
        title = 'Alfred Project'


class ProjectUpdate(Project):
    logic: Optional[dict]
    fields: Optional[List]
    edl: Optional[Edl]
