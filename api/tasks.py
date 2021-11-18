from celery import Celery, Task
from otto.render import renderMultitrack
from otto.models import Edl
import config
from logger import DbLogger
from os.path import join
from bucket import upload

renderer = Celery('renderer', backend=config.CELERY_BACKEND, broker=config.CELERY_BROKER)

renderer.config_from_object(config.CeleryConfig)

class Renderer(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print('failed task', self, exc, task_id, args, kwargs, einfo)
        self.log.failed()
        

@renderer.task(bind=True, base=Renderer)
def renderRemote(self, 
        edl: Edl,
        filename, 
        audio=None, 
        moviesize=(1920,1080), 
        fps=30.0,
        bitrate=None,
        ffmpeg_params=None, 
        **kwargs):
    try:
        self.log = DbLogger(self, filename)
        renderMultitrack(edl=edl, 
            audio=audio, 
            filename=join('videos', filename), 
            logger=self.log, 
            moviesize=moviesize,
            fps=fps,
            bitrate=bitrate,
            ffmpeg_params=ffmpeg_params)
        upload(filename, directory='videos')
        # self.update_state(state='PROGRESS', meta={'status': 'uploaded'})
        self.log.uploaded()
    except Exception as e:
        print('error executing render task', filename, e)
        self.log.failed(filename=filename, exc=e)
