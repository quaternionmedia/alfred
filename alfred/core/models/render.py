from typing import Optional, List
from datetime import datetime
from beanie import Document
from otto.models import Edl
from fastapi import Query
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
    link: Optional[str]
    username: Optional[str]
    filename: Optional[str]

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
    link: Optional[str]
    filename: Optional[str]
