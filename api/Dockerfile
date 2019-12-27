FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7-alpine3.8
RUN pip install -U pip
RUN pip install aiofiles

ENTRYPOINT ["/start-reload.sh"]
