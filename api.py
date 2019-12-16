from fastapi import FastAPI, Path, Body
from starlette.staticfiles import StaticFiles
from uvicorn import run
from os import environ
from urllib.request import urlopen
from subprocess import run as bash

def seconds(t):
    return sum(x * int(s) for x, s in zip([3600, 60, 1], t.split(":")))

app = FastAPI()

@app.get('/edl')
def edit():
    url = 'https://docs.google.com/spreadsheets/d/1SsnasrOJWoKMXZiLiPYkRp2yRcB_IagqkAcMRoiMgSY/export?format=csv'
    edl = urlopen(url).read().decode().split('\r\n')
    # [filename, inpoint, outpoint, duration, description]
    with open('edl.edl', 'w') as f:
        for clip in edl[1:]:
            clip = clip.split(',')
            print(clip)
            f.write(f'file videos/{clip[0]}\ninpoint {clip[1]}\noutpoint {clip[2]}\n\n')
    print(bash(['ffmpeg', '-f', 'concat', '-i', 'edl.edl', '-c', 'copy', 'videos/output.mp4']).stdout)
    with open('chapters.meta', 'w') as f:
        f.write(';FFMETADATA1\n\n')
        t = 0
        for clip in edl[1:]:
            clip = clip.split(',')
            d = seconds(clip[2]) - seconds(clip[1])
            end = t + d
            f.write(f'[CHAPTER]\nTIMEBASE=1/1\nSTART={t}\nEND={end}\ntitle={clip[4]}\n\n')
            t += d
    return str(bash(['ffmpeg', '-i', 'videos/output.mp4', '-i', 'chapters.meta', '-codec', 'copy', 'videos/out.mp4']).returncode)

app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
