from celery import Celery
from otto.render import renderEdl
import config
from logger import celeryLogger

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

@renderer.task
def renderRemote(edl, media, audio, filename, moviesize, logger=None):
    renderEdl(edl, media, audio, filename, moviesize, celeryLogger(filename))
