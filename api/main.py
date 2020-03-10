from fastapi import FastAPI, Path, Body, Header
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from partial import PartialFileResponse
from uvicorn import run
from os.path import join
from urllib.request import urlopen
from subprocess import run as bash
from db import db


def seconds(t):
    return sum(x * round(float(s), 2) for x, s in zip([3600, 60, 1], t.split(":")))


def getEdl(edlName='test.csv'):
    with open(join('/app/dist/', edlName), 'r') as f:
        return f.read().strip().split('\n')[1:]

# Saves an EDL file to Filesystem.  Takes .edl and returns Boolean confirmation.
def saveEdl(edl):
    # [filename, inpoint, outpoint, duration, description]
    with open('/app/dist/edl.edl', 'w') as f:
        for clip in edl:
            clip = clip.split(',')
            # print(clip)
            filename = join('/app/', clip[0])
            f.write(f'file {filename}\ninpoint {clip[1]}\noutpoint {clip[2]}\n\n')

# Depreciated(ing) bash version of rendering.
def bashRenderEdl(edl, filename):
    saveEdl(edl)
    print('rendering', edl, filename)
    print(bash(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', '/app/dist/edl.edl', '-c', 'copy', '-y', join('videos/', filename)]).stdout)
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


# REST Routing :
# TODO: as it grows length -> breakout file into suporting files as needed, e.g. dbm'database manager', util'utiliy', etc.
app = FastAPI()

@app.get('/edl')
def returnEdl():
    edl = []
    for clip in getEdl():
        print(clip, type(clip))
        clip = clip.split(',')
        edl.append([clip[0],
            seconds(clip[1]),
            seconds(clip[2]),
            seconds(clip[3]),
            *clip[4:]])
    return edl


@app.get('/edit')
def edit():
    edl = getEdl()
    saveEdl(edl)


@app.get('/render')
def render(edl: str = 'test.csv'):
    return bashRenderEdl(getEdl(edl), filename=edl + '.mp4')


@app.get('/renders')
def renders():
    # returns list of current renders
    return


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
def getProjects():
    return ['demo.csv', 'external.csv', 'moon.csv', 'train.csv', 'xmas.csv']

@app.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    return PartialFileResponse(join('/app/videos', video))

# Default page to return.
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)