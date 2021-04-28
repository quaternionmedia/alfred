from fastapi import APIRouter, Depends, Body, Query, BackgroundTasks
from typing import List, Optional
from auth import get_current_active_user, User
from otto.models import Edl
from otto.getdata import timestr
from tasks import renderRemote
from os.path import join
from db import db
from config import BUCKET_NAME
from bson.json_util import dumps
from bucket import generate_signed_url

renderAPI = APIRouter()

@renderAPI.post('/render')
async def queueRender(
        project: str, 
        width: int = 1920, 
        height: int = 1080, 
        fps: Optional[float] = Query(30.0),
        quality: Optional[str] = Query(None),
        bitrate: Optional[str] = Query(None),
        ffmpeg_params: Optional[List[str]] = Query(None),
        clips: Edl = Body(...),
        user: User = Depends(get_current_active_user)):
    ts = timestr()
    filename = f'{project}_{width}x{height}{"_" + quality if quality else ""}_{clips.duration}s_{ts}.mp4'
    render = {
        'username': user.username,
        'project': project,
        'filename': filename,
        'duration': clips.duration,
        'resolution': (width, height),
        'fps': fps,
        'quality': quality,
        'bitrate': bitrate,
        'ffmpeg_params': ffmpeg_params,
        'edl': clips.clips,
        'progress': 0,
        'link': join('https://storage.googleapis.com/', BUCKET_NAME, filename),
        }
    # media = db.projects.find_one({'name': project}, ['form'])['form']['media']
    id = db.renders.insert_one(render).inserted_id
    print('rendering!', render)
    task = renderRemote.delay(
        edl=clips.clips, 
        filename=filename, 
        moviesize=(width, height), 
        fps=fps, 
        bitrate=bitrate,
        ffmpeg_params=ffmpeg_params)
    return str(id)

@renderAPI.get('/render')
def getSignedRenderLink(name: str, user: User = Depends(get_current_active_user)):
    return generate_signed_url(name)


@renderAPI.get('/renders')
def renders(user: User = Depends(get_current_active_user)):
    return dumps(db.renders.find({}, ['filename', 'progress', 'link', 'project', 'resolution', 'quality', 'duration']).sort([('_id', -1)]))


@renderAPI.get('/renders/{render}')
def rendersInfo(user: User = Depends(get_current_active_user)):
    info = { 'edl': render, 'progress': 0, 'link': '', 'paused': False }
    return info


@renderAPI.put('/renders/{render}/pause')
def pauseRender(user: User = Depends(get_current_active_user)):
    # pause selected render
    return


@renderAPI.put('/renders/{render}/cancel')
def cancelRender(render: str, user: User = Depends(get_current_active_user)):
    # cancel selected render
    res = db.renders.delete_one({'filename': render})
    if res.deleted_count:
        print('deleted render', render, res, res.deleted_count)
        return res.deleted_count
    else:
        return HTTPException(status_code=406, detail='no such entry in database')
