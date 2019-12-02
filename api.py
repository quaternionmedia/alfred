from fastapi import FastAPI, Path, Body
from starlette.staticfiles import StaticFiles
from uvicorn import run
from os import environ

# port = int(environ['UVICON_PORT'])

app = FastAPI()

app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
