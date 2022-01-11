FROM mher/flower

RUN pip3 install -U celery pymongo

CMD ["celery", "flower", "--port=5555"]
