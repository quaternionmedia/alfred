FROM python

WORKDIR /app
RUN pip3 install numpy
RUN mkdir -p data

COPY pyproject.toml README.md ./
COPY alfred alfred

RUN BEZIER_NO_EXTENSION=true pip3 install -e alfred/otto[render]
RUN pip3 install -e . uvicorn

RUN rm /etc/ImageMagick-6/policy.xml
COPY alfred/otto/fonts /usr/share/fonts/truetype
RUN fc-cache -f -v

CMD ["uvicorn", "alfred.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
