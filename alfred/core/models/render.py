from typing import Optional, List
from beanie import Document
from otto.models import Edl
from beanie import PydanticObjectId


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
    quality: Optional[str]
    bitrate: Optional[List]
    ffmpeg_params: Optional[List[str]]
    progress: Optional[float]
    # Written by DbLogger throughout the encode and never modelled here, so the
    # API dropped it on the way out: a caller could see progress reach 100 and
    # still have no way to tell a finished render from a failed one. That is
    # the field anything waiting on a render needs.
    status: Optional[str]
    link: Optional[str]
    username: Optional[str]
    filename: Optional[str]
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
