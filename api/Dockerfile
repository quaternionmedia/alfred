FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7-alpine3.8

RUN apk add  --no-cache ffmpeg

RUN pip install -U pip
RUN pip install aiofiles ffmpeg-python tinydb


ENTRYPOINT ["/start-reload.sh"]
