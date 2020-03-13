FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7-alpine3.8

RUN apk add  --no-cache ffmpeg
RUN apk add g++

RUN pip install -U pip

RUN apk add libffi-dev openssl-dev
COPY requirements.txt /
RUN pip install -Ur /requirements.txt

ENTRYPOINT ["/start-reload.sh"]
