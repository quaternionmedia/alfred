FROM dpokidov/imagemagick:latest

RUN apt update
RUN apt install -y python3 python3-pip python3-setuptools
RUN apt install -y ffmpeg git
RUN apt install -y libjpeg-dev libcairo2 libcairo-dev

WORKDIR /app
RUN mkdir -p /app/data/

RUN pip3 install -U pip
RUN pip3 install --pre moviepy

COPY alfred/ /alfred/alfred

RUN pip3 install -Ur /alfred/alfred/requirements.txt
RUN pip3 install -Ur /alfred/alfred/otto/requirements.txt

RUN pip3 install --user -e /alfred/alfred/otto/


COPY /setup.py /alfred/
RUN pip3 install --user -e /alfred/

COPY alfred/otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
