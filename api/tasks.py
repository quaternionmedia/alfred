from celery import Celery
from otto.render import renderMultitrack
import config
from logger import DbLogger
from os.path import join
from bucket import upload

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)


@renderer.task(bind=True)
def renderRemote(self, edl, filename, audio=None, moviesize=(1920,1080)):
    log = DbLogger(self, filename)
    renderMultitrack(edl, audio, join('videos', filename), moviesize, log)
    upload(filename, directory='videos')
    self.update_state(state='PROGRESS', meta={'status': 'uploaded'})
