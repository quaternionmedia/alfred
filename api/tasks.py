from celery import Celery
from otto.render import renderEdl
import config
from logger import CeleryLogger
from google.cloud import storage
from config import BUCKET_NAME
from os.path import join

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

def upload(filename, directory=None, location=BUCKET_NAME):
    client = storage.Client()
    bucket = client.bucket(location)

    blob = bucket.blob(filename)
    blob.upload_from_filename(join(directory, filename) if directory else filename)

@renderer.task(bind=True)
def renderRemote(self, edl, media, audio, filename, moviesize):
    log = CeleryLogger(self)
    renderEdl(edl, media, audio, join('videos', filename), moviesize, log)
    upload(filename, directory='videos')
    self.update_state(state='PROGRESS', meta={'status': 'uploaded'})
