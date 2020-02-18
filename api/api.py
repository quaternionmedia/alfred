from fastapi import FastAPI, Path, Body, Header
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from partial import PartialFileResponse
from uvicorn import run
from os.path import join
from urllib.request import urlopen
from subprocess import run as bash

from db import db

def csvToEdl():
    with open('dist/edl.csv', 'w') as f:
        for clip in edl:
            clip = clip.split(',')
            # print(clip)
            f.write(f'file videos/{clip[0]}\ninpoint {clip[1]}\noutpoint {clip[2]}\n\n')

# def edlToDB():
#     db.insert(





def seconds(t):
    return sum(x * int(s) for x, s in zip([3600, 60, 1], t.split(":")))

def getEdl():
#return urlopen(url).read().decode().split('\r\n')[1:]
    with open('dist/edl.csv', 'r') as f:
        return f.read().split('\n')[1:]



def saveEdl(edl):
    # [filename, inpoint, outpoint, duration, description]
    with open('dist/edl.edl', 'w') as f:
        for clip in edl:
            clip = clip.split(',')
            # print(clip)
            f.write(f'file videos/{clip[0]}\ninpoint {clip[1]}\noutpoint {clip[2]}\n\n')
def bashRenderEdl(edl):
    print(bash(['ffmpeg', '-f', 'concat', '-i', 'edl.edl', '-c', 'copy', 'videos/output.mp4']).stdout)
    with open('chapters.meta', 'w') as f:
        f.write(';FFMETADATA1\n\n')
        t = 0
        for clip in edl:
            clip = clip.split(',')
            d = seconds(clip[2]) - seconds(clip[1])
            end = t + d
            f.write(f'[CHAPTER]\nTIMEBASE=1/1\nSTART={t}\nEND={end}\ntitle={clip[4]}\n\n')
            t += d
    return str(bash(['ffmpeg', '-i', 'videos/output.mp4', '-i', 'chapters.meta', '-codec', 'copy', 'videos/out.mp4']).returncode)



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
def render():
    return bashRenderEdl(getEdl())

@app.get('/renders')
def renders():
    return getEdl();

@app.get('/renders/{render}')
def rendersInfo():
    info = { 'ed': '', 'progress': 0, 'link': '', 'paused': False }
    return info

@app.put('/renders/{render}/pause')
def pauseRender():
    #{render}.pause
    return True

@app.put('/renders/{render}/cancel')
def cancelRender():
    #{render}.cancel
    return True

@app.get('/projects')
def getProjects():
    return ['edl.csv', 'test.csv']

@app.get('/videos/{video}', responses={
    206: {'content': {'video/mp4': {}},
    'description': 'partial video response'}
    })
async def buffer(video:str, response: Response, bits: int = Header(0)):
    return PartialFileResponse(join('/app/videos', video))

app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
