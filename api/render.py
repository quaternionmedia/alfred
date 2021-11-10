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

def deOid(results: List):
    """De-ObjectID
    Takes a list of objects, and converts the objectID (_id) to a string for serialization"""
    for r in results:
        r['_id'] = str(r['_id'])
    return results

@renderAPI.post('/render')
async def queueRender(
        project: str, 
        width: int = 1920, 
        height: int = 1080, 
        fps: Optional[float] = Query(30.0),
        quality: Optional[str] = Query(None),
        bitrate: Optional[str] = Query(None),
        ffmpeg_params: Optional[List[str]] = Query(None),
        description: Optional[str] = Query(None),
        clips: Edl = Body(...),
        user: User = Depends(get_current_active_user)):
    ts = timestr()
    filename = f'{project}{"_" + description if description else ""}_{width}x{height}{"_" + quality if quality else ""}_{clips.duration}s_{ts}.mp4'
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
        'description': description,
        'edl': clips.clips,
        'progress': 0,
        'link': join('https://storage.googleapis.com/', BUCKET_NAME, filename),
        }
    # media = db.projects.find_one({'name': project}, ['form'])['form']['media']
    result = await db.renders.insert_one(render)
    print('rendering!', render)
    task = renderRemote.delay(
        edl=clips.clips, 
        filename=filename, 
        moviesize=(width, height), 
        fps=fps, 
        bitrate=bitrate,
        ffmpeg_params=ffmpeg_params)
    return str(result.inserted_id)

@renderAPI.get('/render')
async def getSignedRenderLink(name: str, user: User = Depends(current_active_user)):
    return generate_signed_url(name)


@renderAPI.get('/renders')
async def renders(user: User = Depends(current_active_user)):
    return deOid(await db.renders.find({}, ['filename', 'progress', 'link', 'project', 'resolution', 'quality', 'duration', 'description']).sort([('_id', -1)]).to_list(100))



@renderAPI.get('/renders/{render}')
async def rendersInfo(user: User = Depends(current_active_user)):
    info = { 'edl': render, 'progress': 0, 'link': '', 'paused': False }
    return info


@renderAPI.put('/renders/{render}/pause')
async def pauseRender(user: User = Depends(current_active_user)):
    # pause selected render
    return


@renderAPI.put('/renders/{render}/cancel')
async def cancelRender(render: str, user: User = Depends(current_active_user)):
    # cancel selected render
    res = await db.renders.find_one_and_delete({'filename': render})
    if res:
        print('deleted render', render, res)
        await db.deleted.insert_one(res)
    else:
        return HTTPException(status_code=406, detail='no such entry in database')
