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
from auth import auth, get_current_active_user, User, Edl
from bson.json_util import dumps, ObjectId

from db import db
from users import users
from logger import DbLogger
from seed import seed, formToEdl
from tasks import renderRemote

from otto.main import app as ottoApi
from otto.render import renderEdl, renderForm
from otto.getdata import timestr, download
from otto.models import Edl, VideoForm

from moviepy.editor import ImageClip, VideoFileClip
from math import floor

def seconds(t):
    return sum(x * round(float(s), 2) for x, s in zip([3600, 60, 1], t.split(":")))


def getEdl(filename='test.csv'):
    results = db.edls.find_one({'filename': filename})
    if results:
        return results['edl']
    else:
        if isfile(join('dist', filename)):
            with open(join('dist', filename), 'r') as f:
                return f.read()
                # return f.read().strip().split('\n')[1:]
        else:
            return False

# Takes an Edl and saves an ffmpeg text file to filesystem.
def saveFFConcat(edl, filename):
    filename = join('/app', filename)
    with open(filename, 'w') as f:
        for clip in edl:
            # clip = clip.split(',')
            # print(clip)
            f.write(f'file {clip[0]}\ninpoint {clip[1]:.2f}\noutpoint {clip[2]:.2f}\n\n')

# Depreciated(ing) bash version of rendering.
def bashRenderEdl(edl, filename):
    edlName = filename + '.edl'
    saveFFConcat(edl, edlName)
    # print('rendering', edl, filename)
    print(bash(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', join('/app', edlName), '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', '-y', join('videos/', filename)]).stdout)
    return f'rendered! {edl}!'


def bashRenderChapters(edl):
    with open('chapters.meta', 'w') as f:
        f.write(';FFMETADATA1\n\n')
        t = 0
        for clip in edl:
            clip = clip.split(',')
            d = seconds(clip[2]) - seconds(clip[1])
            end = t + d
            f.write(f'[CHAPTER]\nTIMEBASE=1/1\nSTART={t}\nEND={end}\ntitle={clip[4]}\n\n')
            t += d
    return str(bash(['ffmpeg', '-i', join('videos/', edl), '-i', 'chapters.meta', '-codec', 'copy', '-y', join('videos/', edl)]).returncode)


# update db when render progress has changed
def updateProgress(id, progress):
    return db.renders.find_one_and_update({'_id': id}, {'$set': {'progress': progress }})

# REST Routing :
# TODO: as it grows length -> breakout file into suporting files as needed, e.g. dbm'database manager', util'utiliy', etc.
app = FastAPI()
app.mount('/otto', ottoApi)

@app.on_event("startup")
async def seedDb():
    if not db.edls.count_documents({}):
        from seed import seed
        db.edls.insert_many(seed)
    if not db.projects.count_documents({}):
        from otto.defaults import sample_forms
        db.projects.insert_many(sample_forms)

@app.get('/edl')
def returnEdl(filename: str):
    return getEdl(filename)


@app.post('/edl')
async def saveEdl(filename: str, edl: Edl):
    return dumps(db.edls.find_one_and_update({'filename': filename}, {'$set': {'edl': edl.edl}}, upsert=True, new=True))


@app.get('/download')
async def download_file(filename: str):
    return FileResponse(filename, filename=filename)


@app.post('/render')
async def queueRender(edl: Edl, project: str, width: int = 1920, height: int = 1080):
    ts = timestr()
    duration = sum(c['duration'] for c in edl.edl)
    filename = f'{project}_{width}x{height}_{duration}s_{ts}.mp4'
    media = db.projects.find_one({'name': project}, ['form'])['form']['media']
    id = db.renders.insert_one({
        'project': project,
        'filename': filename,
        'duration': duration,
        'resolution': (width, height),
        'media': media,
        'edl': edl.edl,
        'progress': 0,
        'started': ts,
        'link': join('videos', filename),
        }
    ).inserted_id
    proj = db.projects.find_one({'name': project}, ['form'])['form']
    print('rendering!', filename, proj)
    media = [ download(m) for m in proj['media'] ]
    renderRemote.delay(edl.edl, media=media, audio=download(proj['audio'][0]), filename=join('videos', filename), moviesize=(width, height))
    # renderer.add_task(updateProgress, id, 100)
    return str(id)


@app.get('/renders')
def renders(user: User = Depends(get_current_active_user)):
    return dumps(db.renders.find({}, ['filename', 'progress', 'link', 'project', 'resolution', 'duration', 'started']).sort([('_id', -1)]))


@app.get('/renders/{render}')
def rendersInfo(user: User = Depends(get_current_active_user)):
    info = { 'edl': render, 'progress': 0, 'link': '', 'paused': False }
    return info


@app.put('/renders/{render}/pause')
def pauseRender(user: User = Depends(get_current_active_user)):
    # pause selected render
    return


@app.put('/renders/{render}/cancel')
def cancelRender(render: str, user: User = Depends(get_current_active_user)):
    # cancel selected render
    res = db.renders.delete_one({'filename': render})
    if res.deleted_count:
        print('deleted render', render, res, res.deleted_count)
        return res.deleted_count
    else:
        return HTTPException(status_code=406, detail='no such entry in database')


@app.get('/edls')
def getEdls(user: User = Depends(get_current_active_user)):
    return [i['filename'] for i in db.edls.find({}, ['filename'])]

@app.get('/templates')
async def getTemplates():
    return seed[0]['edl']

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
    form.media = [ m.strip() for m in form.media[0].split(',') ]
    result = db.projects.update_one({'name': project}, {'$set': {'form': dict(form)}}, upsert=True)
    print('saved form', project, form, result)
    return result.modified_count

@app.post('/formToEdl')
async def form_to_edl(form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media[0].split(',') ]
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
    form.media = [ m.strip() for m in form.media[0].split(',') ]
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

app.include_router(auth)
app.include_router(users)

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
