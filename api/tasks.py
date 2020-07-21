from celery import Celery
from otto.render import renderEdl
import config
from logger import CeleryLogger
from google.cloud import storage
from config import BUCKET_NAME

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

def upload(filename, location=BUCKET_NAME):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_filename(filename)

@renderer.task(bind=True)
def renderRemote(self, edl, media, audio, filename, moviesize):
    renderEdl(edl, media, audio, filename, moviesize, CeleryLogger(self))
    upload(filename)
