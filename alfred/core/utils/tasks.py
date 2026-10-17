from os.path import join

from celery import Celery, Task
from otto.models import Edl
from otto.render import renderMultitrack

from alfred import config

from ..models.render import is_output_filename
from .bucket import upload
from .encoding import preset_for
from .logger import DbLogger
from .media import resolve_edl

renderer = Celery(
    'renderer',
    backend=config.CELERY_BACKEND,
    broker=config.CELERY_BROKER,
    # The module that defines the tasks, by its package name.
    #
    # This also listed 'core.utils.tasks', which only imports with alfred/ as
    # the working directory -- the reason the worker was started with
    # `--workdir /app/alfred`. Importing the same file under a second name
    # registered every task twice (`core.utils.tasks.renderRemote` beside the
    # real one), and the working directory it forced is what made a library
    # path like `videos/x.mp4` resolve to /app/alfred/videos, where nothing is.
    include=['alfred.core.utils.tasks'],
)

renderer.config_from_object(config.CeleryConfig)


class Renderer(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print('failed task', self, exc, task_id, args, kwargs, einfo)
        self.log.failed()


@renderer.task(bind=True, base=Renderer)
def renderRemote(
    self,
    edl: dict,
    filename: str,
    renderId: str,
    audio=None,
    moviesize=(1920, 1080),
    fps=30.0,
    quality=None,
    **kwargs,
):
    """Render one EDL to `filename`.

    Arguments arrive as JSON (contract C7): the EDL as a dict, which is parsed
    back into an `Edl` here, the render id as a string, the size as a list.
    Encoding comes from the named `quality` preset (C5). Any `bitrate` or
    `ffmpeg_params` in `kwargs` -- from a job queued before presets -- is
    ignored rather than handed to ffmpeg.
    """
    try:
        self.log = DbLogger(self, renderId)
        # Only a name `output_filename` could have produced, so the path is
        # always a file directly inside the output directory. Checked here as
        # well as decided by the api, because a stored render's filename was
        # built from its request and could hold `../`.
        if not is_output_filename(filename):
            raise ValueError(f'refusing to write a render to {filename!r}')
        # Media names resolved here, against VIDEO_DIR, rather than handed to
        # the engine as sent. The engine opens a relative name against the
        # worker's working directory, which is not where the library is, and
        # an absolute one wherever it points. The api has already refused
        # anything outside the library; checking again here covers EDLs that
        # were stored before that check existed and are re-queued now.
        timeline = resolve_edl(Edl.parse_obj(edl))
        renderMultitrack(
            edl=timeline,
            audio=audio,
            filename=join(config.VIDEO_DIR, filename),
            logger=self.log,
            moviesize=tuple(moviesize),
            fps=fps,
            **preset_for(quality, strict=False).encoder_args(),
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
        upload(filename, directory=config.VIDEO_DIR)
    except Exception as e:
        print('render succeeded but the automatic upload did not', renderId, e)
        return

    self.log.uploaded()
