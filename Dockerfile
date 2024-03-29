FROM python

WORKDIR /app
RUN mkdir -p data

COPY pyproject.toml README.md ./
COPY alfred alfred

RUN BEZIER_NO_EXTENSION=true pip3 install -e alfred/otto[render]
RUN pip3 install -e . uvicorn

RUN rm /etc/ImageMagick-6/policy.xml

CMD ["uvicorn", "alfred.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
