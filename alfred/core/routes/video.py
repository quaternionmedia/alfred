from fastapi import APIRouter, Header
from ..utils.db import db
from os import listdir
from os.path import join
from ..responses import PartialFileResponse
from starlette.responses import Response, FileResponse

from moviepy.editor import ImageClip, VideoFileClip
from math import floor

videoAPI = APIRouter()


@videoAPI.get('/videos')
async def getVideos():
    """# videos
Get a list of all videos available locally on this instance"""
    return [join('videos', f) for f in listdir('videos')]

@videoAPI.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    """# video
Get a specific video by filename.

Returns an `HTTP 206 Partial Content` response, allowing the client to jump to a specific potion of a large video file."""
    return PartialFileResponse(join('/app/videos', video))

@videoAPI.get('/projects')
async def getProjects():
    """# Get projects
Returns a list of all project names available."""
    return [p['name'] for p in await db.projects.find({}, { 'name': 1, '_id': 0 }).to_list(length=100)]
    

@videoAPI.get('/project/{project}')
async def getProject(project: str):
    return await db.projects.find_one({'name': project}, {'_id': 0})
    
