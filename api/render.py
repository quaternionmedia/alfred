from fastapi import APIRouter, Depends, Body, BackgroundTasks
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
async def queueRender(prog: BackgroundTasks, project: str, width: int = 1920, height: int = 1080, edl: Edl = Body(...), user: User = Depends(get_current_active_user)):
    ts = timestr()
    filename = f'{project}_{width}x{height}_{edl.duration}s_{ts}.mp4'
    render = {
        'username': user.username,
        'project': project,
        'filename': filename,
        'duration': edl.duration,
        'resolution': (width, height),
        'edl': edl.edl,
        'progress': 0,
        'started': ts,
        'link': join('https://storage.googleapis.com/', BUCKET_NAME, filename),
        }
    # media = db.projects.find_one({'name': project}, ['form'])['form']['media']
    id = db.renders.insert_one(render).inserted_id
    print('rendering!', render)
    task = renderRemote.delay(edl=edl.edl, filename=filename, moviesize=(width, height))
    def updateRenderProgress(progress):
        r = progress.get('result')
        # print('updating progress', r)
        if r:
            if r.get('index'):
                p = max((100 * r['index'] / r['total']) - 1, 0)
                db.renders.update_one({'filename': filename}, {'$set': {'progress': p}})
            elif r.get('status') == 'uploaded':
                db.renders.update_one({'filename': filename}, {'$set': {'progress': 100}})
            else:
                print('got other progress message', r)
        else:
            print('got other message', progress)
    prog.add_task(task.get,
                    on_message = updateRenderProgress,
                    propagate=False)
    return str(id)

@renderAPI.get('/render')
def getSignedRenderLink(name: str, user: User = Depends(get_current_active_user)):
    return generate_signed_url(name)


@renderAPI.get('/renders')
def renders(user: User = Depends(get_current_active_user)):
    return dumps(db.renders.find({}, ['filename', 'progress', 'link', 'project', 'resolution', 'duration', 'started']).sort([('_id', -1)]))


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
