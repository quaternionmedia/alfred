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


# RUN apt install -y imagemagick imagemagick-common
RUN apt install -y build-essential wget
RUN wget https://imagemagick.org/archive/binaries/magick
RUN chmod +x magick
RUN mv magick /usr/local/bin/magick
# ENV IMAGEMAGICK_BINARY=/usr/local/bin/magick
# RUN ln -s /usr/local/bin/magick /usr/local/bin/magick.exe

# fonts
# RUN apt install -y ttf-mscorefonts-installer fontconfig
# RUN update-ms-fonts


# COPY --from=builder /magick /usr/local/bin/magick
COPY --from=builder /kburns-slideshow /kburns
RUN chmod +x /kburns/main.py
RUN ln -s /kburns/main.py /usr/bin/kburns
RUN ln -s /usr/bin/ffmpeg /usr/bin/ffmpeg.exe
RUN ln -s /usr/bin/ffprobe /usr/bin/ffprobe.exe

WORKDIR /app
RUN mkdir -p /app/data/


COPY alfred/otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv

RUN pip3 install -U pip setuptools
RUN pip3 install --pre moviepy


COPY alfred/requirements.txt /
RUN pip3 install -Ur /requirements.txt
COPY alfred/otto/requirements.txt /otto_requirements.txt
RUN pip3 install numpy gizeh pillow
RUN BEZIER_NO_EXTENSION=true pip3 install bezier
RUN pip3 install -Ur /otto_requirements.txt
COPY alfred/otto /otto
RUN pip install -e /otto/
COPY alfred/ /alfred/alfred
COPY /setup.py /alfred/
RUN pip install -e /alfred/
# CMD ["/start-reload.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
