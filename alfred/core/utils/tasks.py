from os.path import join

from celery import Celery, Task
from otto.models import Edl
from otto.render import renderMultitrack

from alfred import config
from alfred.config import VIDEO_DIR

from .bucket import upload
from .logger import DbLogger

renderer = Celery(
    'renderer',
    backend=config.CELERY_BACKEND,
    broker=config.CELERY_BROKER,
    include=[
        'alfred.core.utils',
        'core.utils.tasks',
    ],
)

renderer.config_from_object(config.CeleryConfig)


class Renderer(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print('failed task', self, exc, task_id, args, kwargs, einfo)
        self.log.failed()


@renderer.task(bind=True, base=Renderer)
def renderRemote(
    self,
    edl: Edl,
    filename: str,
    renderId: str,
    audio=None,
    moviesize=(1920, 1080),
    fps=30.0,
    bitrate=None,
    ffmpeg_params=None,
    **kwargs,
):
    try:
        self.log = DbLogger(self, renderId)
        renderMultitrack(
            edl=edl,
            audio=audio,
            filename=join(VIDEO_DIR, filename),
            logger=self.log,
            moviesize=moviesize,
            fps=fps,
            bitrate=bitrate,
            ffmpeg_params=ffmpeg_params,
        )
    except Exception as e:
        print('error executing render task', renderId, e)
        self.log.failed(filename=renderId, exc=e)
        return

    # The render is finished and the file exists. Say so before attempting to
    # put it anywhere, because those are separate outcomes.
    self.log.rendered()

    # Uploading is now one destination among several, reachable explicitly via
    # POST /render/{id}/deliver. Attempt it here for the deployments that
    # depended on it happening automatically, but do not let it fail the
    # render: this ran inside the same try as the encode, so a missing
    # credentials file marked a perfectly good video as a failed render. On a
    # checkout without GCS credentials that is every render -- docker creates
    # the absent ./cred.json as a directory, and the upload dies with
    # IsADirectoryError long after the video is safely on disk.
    try:
        upload(filename, directory=VIDEO_DIR)
    except Exception as e:
        print('render succeeded but the automatic upload did not', renderId, e)
        return

    self.log.uploaded()
