FROM alpine AS builder
RUN apk add git
RUN git clone https://github.com/quaternionmedia/kburns-slideshow.git

FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7-alpine3.8
RUN apk update
RUN pip install -U pip

RUN apk add  --no-cache ffmpeg
RUN apk add g++ wget libffi-dev openssl-dev jpeg-dev cairo cairo-dev imagemagick

COPY requirements.txt /
RUN pip install -Ur /requirements.txt
RUN pip install numpy gizeh pillow
RUN pip install celery google-cloud-storage

COPY --from=builder /kburns-slideshow /kburns
RUN chmod +x /kburns/main.py
RUN ln -s /kburns/main.py /usr/bin/kburns
RUN ln -s /usr/bin/ffmpeg /usr/bin/ffmpeg.exe
RUN ln -s /usr/bin/ffprobe /usr/bin/ffprobe.exe

COPY otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv
RUN pip install jinja2
RUN pip install --pre moviepy
ENV IMAGEMAGICK_BINARY=/usr/bin/magick

RUN mkdir -p /app/data/
COPY /otto /otto
RUN pip install /otto/
CMD ["/start-reload.sh"]
