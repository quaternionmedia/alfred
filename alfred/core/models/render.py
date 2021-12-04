from typing import Optional, List
from datetime import datetime
from beanie import Document
from otto.models import Edl
from fastapi import Query

class Render(Document):
    edl: Edl
    name: Optional[str]
    project: Optional[str]
    description: Optional[str]
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
    description: Optional[str]
    resolution: Optional[str]
    quality: Optional[List]
    progress: Optional[float]
    link: Optional[str]
