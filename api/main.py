from fastapi import FastAPI, Path, Body, Header, Depends, BackgroundTasks, Form, HTTPException, File, UploadFile
from starlette.staticfiles import StaticFiles
from starlette.responses import Response, FileResponse
from typing import List
from partial import PartialFileResponse
from uvicorn import run
from os.path import join, isfile
from os import listdir
from urllib.request import urlopen
from subprocess import run as bash
from auth import auth, get_current_active_user, User
from bson.json_util import dumps

from db import db
from users import users
from logger import DbLogger
from seed import seed, formToEdl

from render import renderAPI
from otto.main import app as ottoApi

from otto.render import renderForm
from otto.getdata import timestr, download
from otto.models import Edl, VideoForm
from otto import templates

from moviepy.editor import ImageClip, VideoFileClip
from math import floor
from emailer import sendMail

def seconds(t):
    return sum(x * round(float(s), 2) for x, s in zip([3600, 60, 1], t.split(":")))


app = FastAPI()

@app.on_event("startup")
async def seedDb():
    if not db.edls.count_documents({}):
        from seed import seed
        db.edls.insert_many(seed)
    if not db.projects.count_documents({}):
        from otto.defaults import sample_forms
        db.projects.insert_many(sample_forms)

@app.on_event('startup')
async def checkFonts():
    fonts = bash(['fc-list', '-f', '"%{family}-%{style}\n"'], capture_output=True).stdout.decode().replace('"', '').split('\n')
    results = []
    for f in fonts:
        if f:
            font = f.split('-')
            for fam in font[0].split(','):
                db.fonts.update_one({'family': fam.replace(' ', '-')}, {'$set': { 'style': [i.replace(' ', '-') for i in font[1].split(',')] }}, upsert=True)
    # db.fonts.update_many(results, upsert=True)

@app.get('/fonts')
def getFonts():
    return [i['family'] for i in db.fonts.find({}, ['family'])]

@app.post('/edl')
async def saveEdl(filename: str, edl: Edl):
    return dumps(db.edls.find_one_and_update({'filename': filename}, {'$set': {'edl': edl.edl}}, upsert=True, new=True))

@app.get('/download')
async def download_file(filename: str):
    return FileResponse(filename, filename=filename)

@app.get('/templates')
async def getTemplates():
    # return seed[0]['edl']
    return [t for t in dir(templates) if t.islower() and t[0] is not '_']

@app.get('/videos')
async def getVideos():
    return [join('videos', f) for f in listdir('videos')]

@app.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    return PartialFileResponse(join('/app/videos', video))

@app.get('/data/{media}')
async def getMedia(media: str):
    return FileResponse(join('data', media))

@app.get('/projects')
async def getProjects():
    return [ p['name'] for p in db.projects.find({})]

@app.get('/project/{project}')
async def getProject(project: str):
    c = db.projects.find_one({'name': project}, ['name', 'form', 'edl'])
    res = {}
    for a in ['name', 'edl', 'form']:
        if c.get(a):
            res[a] = c.get(a)
    return res

@app.post('/save')
async def saveForm(project: str, form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media.split(',') ]
    form.audio = [ m.strip() for m in form.audio.split(',') ]
    result = db.projects.update_one({'name': project}, {'$set': {'form': dict(form)}}, upsert=True)
    print('saved form', project, form, result)
    return result.modified_count

@app.post('/formToEdl')
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

@app.get('/bkg/{project}')
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

@app.post('/form')
async def form_to_video(renderer: BackgroundTasks, form: VideoForm = Depends(VideoForm.as_form)):
    filename = f'{timestr()}_{form.project}.mp4'
    form.media = [ m.strip() for m in form.media.split(',') ]
    print('rendering video from form', form, filename)
    db.renders.insert_one(
        {'filename': filename,
        'form': dict(form),
        'progress': 0,
        'link': join('videos', filename),
        })
    renderer.add_task(renderForm, form=dict(form), filename=join('videos', filename), logger=DbLogger(filename))
    return filename

@app.post('/upload')
async def upload(file: UploadFile = File(...)):
    print('saving files', file.filename)
    await saveFile(file)
    return {'filename': join('data', file.filename)}

async def saveFile(file, location='data'):
    data = await file.read()
    with open(join(location, file.filename), 'wb') as f:
        f.write(data)

@app.post('/report')
async def reportIssue(name: str, issue: str = Body(...)):
    if not sendMail(issue, name):
        print('error reporting issue with ', name, issue)
        raise HTTPException(status_code=500, detail='error sending email')
    
app.include_router(ottoApi, prefix='/otto')#, dependencies=[Depends(get_current_active_user)])
app.include_router(renderAPI, dependencies=[Depends(get_current_active_user)])
app.include_router(auth)
app.include_router(users)

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
