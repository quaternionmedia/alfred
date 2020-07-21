from celery import Celery
from otto.render import renderEdl
import config
from logger import CeleryLogger

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

@renderer.task(bind=True)
def renderRemote(self, edl, media, audio, filename, moviesize, logger=None):
    renderEdl(edl, media, audio, filename, moviesize, CeleryLogger(self))
