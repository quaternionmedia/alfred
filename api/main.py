from fastapi import FastAPI, Path, Body, Header, Depends, BackgroundTasks
from starlette.staticfiles import StaticFiles
from starlette.responses import Response, FileResponse
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

from otto.main import app as ottoApi

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
    if not db.edls.find({}).count():
        from seed import seed
        db.edls.insert_many(seed)

@app.get('/edl')
def returnEdl(filename: str):
    return getEdl(filename)


@app.post('/edl')
async def saveEdl(filename: str, edl: Edl):
    return dumps(db.edls.find_one_and_update({'filename': filename}, {'$set': {'edl': edl.edl}}, upsert=True, new=True))


@app.get('/download')
async def download(filename: str):
    return FileResponse(join('videos', filename), filename=filename)


@app.post('/render')
async def render(render: BackgroundTasks, edl: str = 'test.csv'):
    filename = edl + '.mp4'
    edl = getEdl(edl)
    id = db.renders.insert_one({'filename': filename, 'edl': edl, 'progress': 0, 'link': join('videos', filename)}).inserted_id
    render.add_task(bashRenderEdl, edl, filename=filename)
    render.add_task(updateProgress, id, 100)
    return str(id)


@app.get('/renders')
def renders():
    return dumps(db.renders.find({}, ['filename', 'progress', 'link']))


@app.get('/renders/{render}')
def rendersInfo():
    info = { 'edl': render, 'progress': 0, 'link': '', 'paused': False }
    return info


@app.put('/renders/{render}/pause')
def pauseRender():
    # pause selected render
    return


@app.put('/renders/{render}/cancel')
def cancelRender():
    # cancel selected render
    return


@app.get('/projects')
def getProjects(user: User = Depends(get_current_active_user)):
    return [i['filename'] for i in db.edls.find({}, ['filename'])]

@app.get('/videos')
async def getVideos():
    return [join('videos', f) for f in listdir('videos')]

@app.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    return PartialFileResponse(join('/app/videos', video))

@app.get('/otto')
async def getOtto():
    return [
        {
            'type': 'template',
            'name': 'title',
            'data': {
                'text': 'Business Name'
            },
            'duration': 5,
        },
        {
            'type': 'template',
            'name': 'initial',
            'data': {
                'text': 'initial text'
            },
            'duration': 5,
        },
        {
            'type': 'template',
            'name': 'bullets',
            'data': {
                'text': 'bullet points'
            },
            'duration': 5,
        },
        {
            'type': 'template',
            'name': 'call',
            'data': {
                'text': 'call to action'
            },
            'duration': 5,
        },
        {
            'type': 'template',
            'name': 'ending',
            'data': {
                'text1': 'Business Name',
                'text2': 'address',
                'text3': 'website',
                'text4': 'hours',
            },
            'duration': 5,
        },
    ]

app.include_router(auth)
app.include_router(users)

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
