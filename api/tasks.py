from celery import Celery
from otto.render import renderEdl
import config
from logger import CeleryLogger
from os.path import join
from bucket import upload

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)


@renderer.task(bind=True)
def renderRemote(self, edl, media, audio, filename, moviesize):
    log = CeleryLogger(self)
    renderEdl(edl, media, audio, join('videos', filename), moviesize, log)
    upload(filename, directory='videos')
    self.update_state(state='PROGRESS', meta={'status': 'uploaded'})
