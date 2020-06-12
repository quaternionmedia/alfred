FROM alpine AS builder
RUN apk add openssh-client git
COPY github_key /github_key
RUN eval $(ssh-agent) && \
    ssh-add github_key && \
    ssh-keyscan -H github.com >> /etc/ssh/ssh_known_hosts && \
    git clone git@github.com:quaternionmedia/otto.git /otto
RUN git clone https://github.com/quaternionmedia/kburns-slideshow.git
RUN cd /otto && git checkout pip

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

RUN pip install /otto/
ENTRYPOINT ["/start-reload.sh"]
