from fastapi import APIRouter, Path, Body, Header, Depends, File, UploadFile, BackgroundTasks, HTTPException
from db import db
from bson.json_util import dumps
from os import listdir
from os.path import join
from ..responses import PartialFileResponse
from starlette.responses import Response, FileResponse
from typing import List

from logger import DbLogger


from otto import templates
from otto.getdata import download

from moviepy.editor import ImageClip, VideoFileClip
from math import floor

routes = APIRouter()


@routes.get('/fonts')
async def getFonts():
    """# Get fonts
    Returns a list of all available fonts available to be rendered on this instance"""
    return [i['family'] for i in await db.fonts.find({}, ['family']).to_list(1000)]

@routes.get('/videos')
async def getVideos():
    return [join('videos', f) for f in listdir('videos')]

@routes.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    return PartialFileResponse(join('/app/videos', video))

@routes.get('/projects')
async def getProjects():
    """# Get projects
    Returns a list of all project names available"""
    return [p['name'] for p in await db.projects.find({}, { 'name': 1, '_id': 0 }).to_list(length=100)]
    

@routes.get('/project/{project}')
async def getProject(project: str):
    return await db.projects.find_one({'name': project}, {'_id': 0})
    
