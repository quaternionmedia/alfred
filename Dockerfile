FROM quaternionmedia/alfred-docker:v2

RUN mkdir -p /app/data/

COPY alfred/ /alfred/alfred

RUN pip3 install -e /alfred/alfred/otto/


COPY /setup.py /alfred/
RUN pip3 install -e /alfred/

ENTRYPOINT ["python3.10", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
