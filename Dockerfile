FROM quaternionmedia/alfred-docker:latest

RUN mkdir -p /app/data/

COPY alfred/ /alfred/alfred

RUN pip3 install --user -e /alfred/alfred/otto/


COPY /setup.py /alfred/
RUN pip3 install --user -e /alfred/

COPY alfred/otto/fonts/* /usr/share/fonts/truetype/
RUN fc-cache -fv

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
