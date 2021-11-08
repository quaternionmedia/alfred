from fastapi import APIRouter, Path, Body, Header, Depends, File, UploadFile, BackgroundTasks, HTTPException
from db import db
from bson.json_util import dumps
from os import listdir
from os.path import join
from partial import PartialFileResponse
from starlette.responses import Response, FileResponse
from typing import List

from logger import DbLogger


from seed import formToEdl


from otto.models import Edl, VideoForm
from otto import templates
from otto.getdata import download

from moviepy.editor import ImageClip, VideoFileClip
from math import floor

routes = APIRouter()

@routes.post('/edl')
async def saveEdl(filename: str, edl: Edl):
    return dumps(db.edls.find_one_and_update({'filename': filename}, {'$set': {'edl': edl.clips}}, upsert=True, new=True))

@routes.get('/download')
async def download_file(filename: str):
    return FileResponse(filename, filename=filename)

@routes.get('/fonts')
def getFonts():
    return [i['family'] for i in db.fonts.find({}, ['family'])]

@routes.get('/templates')
async def getTemplates():
    # return seed[0]['edl']
    return [t for t in dir(templates) if t.islower() and t[0] is not '_']

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
    return [ p['name'] for p in db.projects.find({})]

@routes.get('/project/{project}')
async def getProject(project: str):
    res = db.projects.find_one({'name': project})
    del res['_id']
    return res

@routes.post('/save')
async def saveForm(project: str, form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media.split(',') ]
    form.audio = [ m.strip() for m in form.audio.split(',') ]
    result = db.projects.update_one({'name': project}, {'$set': {'form': dict(form)}}, upsert=True)
    print('saved form', project, form, result)
    return result.modified_count

@routes.post('/formToEdl')
async def form_to_edl(form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media.split(',') ]
    form.audio = [ m.strip() for m in form.audio.split(',') ]
    edl = formToEdl(form)
    print('edl from form', edl, dict(form))
    db.projects.update_one({'name': form.project},
        {'$set':
            {
                'form': dict(form),
                'edl': edl['edl'],
            }}, upsert=True)
    return True

@routes.get('/bkg/{project}')
async def get_bkg(project: str, width: int, height: int, t: float):
    clips = db.projects.find_one({'name': project}, ['form'])['form']['media']
    clip = download(clips[floor(t / 5)])
    print('making bkg', clip)
    try:
        if clip.endswith('mp4'):
            clip = VideoFileClip(clip)
        else:
            clip = ImageClip(clip)
        if width >= height:
            clip = clip.resize(width=width)
        else:
            clip = clip.resize(height=height)
        clip.save_frame('bkg.jpg', t=t % 5)
        return FileResponse('bkg.jpg')
    except Exception as e:
        print('error making kburns frame', e)
        raise HTTPException(status_code=500, detail='error making kburns frame')

@routes.post('/upload')
async def upload(file: UploadFile = File(...)):
    print('saving files', file.filename)
    await saveFile(file)
    return {'filename': join('data', file.filename)}

async def saveFile(file, location='data'):
    data = await file.read()
    with open(join(location, file.filename), 'wb') as f:
        f.write(data)

