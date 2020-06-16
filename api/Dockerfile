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

COPY --from=builder /kburns-slideshow /kburns
RUN chmod +x /kburns/main.py
RUN ln -s /kburns/main.py /usr/bin/kburns

COPY otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv
RUN pip install moviepy jinja2
ENV IMAGEMAGICK_BINARY=/usr/bin/magick
COPY /otto /otto
RUN pip install /otto/
ENTRYPOINT ["/start-reload.sh"]
