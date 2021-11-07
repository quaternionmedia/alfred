FROM python
RUN pip install flower
RUN pip install pymongo

CMD ["celery", "flower", "--port=5555"]
