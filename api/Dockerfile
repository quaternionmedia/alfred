FROM alpine AS builder
RUN apk add git wget
RUN git clone https://github.com/quaternionmedia/kburns-slideshow.git
# RUN wget https://download.imagemagick.org/ImageMagick/download/binaries/magick
# RUN chmod +x /magick


FROM python
RUN apt update
RUN apt install -y ffmpeg
# RUN apt install -y g++ wget libffi-dev openssl-dev jpeg-dev cairo cairo-dev imagemagick
RUN apt install -y libjpeg-dev libcairo2 libcairo-dev imagemagick
COPY requirements.txt /
RUN pip install -Ur /requirements.txt
COPY otto/requirements.txt /
RUN pip install numpy gizeh pillow
RUN pip install -Ur /requirements.txt
RUN pip install celery[mongodb] google-cloud-storage

# fonts
# RUN apt install -y ttf-mscorefonts-installer fontconfig
# RUN update-ms-fonts

COPY otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv
RUN pip install jinja2
RUN pip install --pre moviepy


# COPY --from=builder /magick /usr/local/bin/magick
COPY --from=builder /kburns-slideshow /kburns
RUN chmod +x /kburns/main.py
RUN ln -s /kburns/main.py /usr/bin/kburns
RUN ln -s /usr/bin/ffmpeg /usr/bin/ffmpeg.exe
RUN ln -s /usr/bin/ffprobe /usr/bin/ffprobe.exe

# RUN apt install -y imagemagick imagemagick-common
RUN apt install -y build-essential wget
RUN wget https://www.imagemagick.org/download/ImageMagick.tar.gz
RUN tar xvzf ImageMagick.tar.gz -C ImageMagick
RUN cd $(tar tzf ImageMagick.tar.gz | head -1) && ./configure && make && make install && ldconfig /usr/local/lib
# ENV IMAGEMAGICK_BINARY=/usr/local/bin/magick
# RUN ln -s /usr/local/bin/magick /usr/local/bin/magick.exe

WORKDIR /app
RUN mkdir -p /app/data/
COPY /otto /otto
RUN pip install /otto/
# CMD ["/start-reload.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
