from celery import Celery
from otto.render import renderEdl
import config

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

@renderer.task
def renderRemote(edl, media, audio, filename, moviesize, logger):
    renderEdl(edl, media, audio, filename, moviesize, logger)
