from datetime import datetime, timezone
from os import makedirs
from os.path import join

from bson import ObjectId
from celery import Celery, Task
from celery.signals import celeryd_init
from otto.exceptions import EdlException
from otto.models import Edl
from otto.render import renderMultitrack

from alfred import config

from ..models.render import is_output_filename
from . import audio_engine
from .bucket import upload
from .captions import TooManyCaptions, style_to_store
from .db import get_sync_db
from .encoding import preset_for
from .logger import DbLogger, failure_reason, mark_failed
from .media import MediaNameError, RefusedEdl, check_media_name, resolve_edl
from .storage import sweep_remote_cache_now_and_then
from .transcription import NothingToHear, transcribe_timeline

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


def worker_count(timeout=1.0) -> int:
    """How many render workers answer a ping within `timeout` seconds.

    Blocking, for up to `timeout` past the last reply: Celery collects
    replies until none has arrived for that long. Call it off the event loop.
    """
    return len(renderer.control.ping(timeout=timeout) or [])


def pending_count():
    """How many render jobs are waiting in the queue, as the broker counts."""
    with renderer.connection_for_read() as connection:
        declared = connection.default_channel.queue_declare(
            queue=renderer.conf.task_default_queue, passive=True
        )
    return declared.message_count


@celeryd_init.connect
def open_the_broadcast_channel(**kwargs):
    """Make sure this worker will hear pings, and every other broadcast.

    With MongoDB as the broker, a worker hears broadcasts -- the ping `GET
    /health` counts workers with, and every other remote-control command --
    through a tailable cursor on a capped collection. MongoDB kills a
    tailable cursor at once if nothing in the collection matches when it is
    opened, and kombu does not reopen it. On a fresh database there is
    nothing to match, so the first worker ever started heard no broadcast
    for as long as it ran: it rendered perfectly well, and answered no ping,
    so a health check reported no renderer at all. Restarting it fixed it,
    because by then something had been broadcast.

    So before this worker starts consuming, broadcast something harmless: a
    ping nobody waits for. That leaves a message in the collection for the
    worker's cursor to start after. Failing here must not stop the worker;
    it would only be deaf to broadcasts, as it always was.
    """
    try:
        renderer.control.broadcast('ping', reply=False)
    except Exception as exc:  # noqa: BLE001 - the worker must start regardless
        print('could not open the broadcast channel; pings may go unheard', exc)


class Renderer(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Anything that escaped the task: record it on the job's own render.

        This called `self.log.failed()`. The task object is one per worker
        process, so `self.log` was whichever logger the *previous* job had
        left there -- a job failing before it made its own marked some other
        render failed -- and on a fresh process there was none, so the
        handler raised in turn. The render to mark is the one in this job's
        arguments.
        """
        print('failed task', task_id, exc)
        render_id = (kwargs or {}).get('renderId')
        if render_id is None:
            return
        try:
            mark_failed(render_id, failure_reason(exc))
        except Exception as e:  # noqa: BLE001 - nothing else is left to tell
            print('could not record the failure of render', render_id, e)


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
    # A local, not `self.log`: the task object outlives the job.
    log = DbLogger(self, renderId)
    try:
        # Only a name `output_filename` could have produced, so the path is
        # always a file directly inside the output directory. Checked here as
        # well as decided by the api, because a stored render's filename was
        # built from its request and could hold `../`.
        if not is_output_filename(filename):
            raise ValueError(f'refusing to write a render to {filename!r}')
        # Media names resolved here, against VIDEO_DIR, rather than handed to
        # the engine as sent. The engine opens a relative name against the
        # worker's working directory -- /app/alfred, with no `videos/` in it,
        # until this change -- and an absolute one wherever it points. The api
        # has already refused anything outside the library; checking again
        # here covers EDLs stored before that check existed and re-queued now.
        timeline = resolve_edl(Edl.parse_obj(edl))
        # A soundtrack is media too, held to the same rule. The engine used to
        # drop this argument; it honours it now, opening a path or fetching a
        # URL exactly as it would a clip's name. Nothing the api queues sets
        # it, so this only ever refuses or resolves a job built elsewhere.
        soundtrack = None
        if audio is not None:
            try:
                soundtrack = check_media_name(audio)
            except MediaNameError as exc:
                raise MediaNameError(f'soundtrack: {exc}') from exc
        # Into RENDER_DIR, not the media library: written beside the media, a
        # render was listed by `GET /videos` and served by `/videos/{file}` to
        # anyone signed in.
        makedirs(config.RENDER_DIR, exist_ok=True)
        renderMultitrack(
            edl=timeline,
            audio=soundtrack,
            filename=join(config.RENDER_DIR, filename),
            logger=log,
            moviesize=tuple(moviesize),
            fps=fps,
            **preset_for(quality, strict=False).encoder_args(),
        )
    except Exception as e:
        print('error executing render task', renderId, e)
        log.failed(exc=e)
        return

    # The render is finished and the file exists. Say so before attempting to
    # put it anywhere, because those are separate outcomes.
    log.rendered()

    # The worker is what fetches most remote media, so it keeps that cache
    # within its TTL -- at most hourly, and never at the render's expense.
    try:
        sweep_remote_cache_now_and_then()
    except Exception as e:  # noqa: BLE001 - housekeeping must not fail a render
        print('could not sweep the remote media cache', e)

    # Uploading is now one destination among several, reachable explicitly via
    # POST /render/{id}/deliver. Attempt it here for the deployments that
    # depended on it happening automatically, but do not let it fail the
    # render: this ran inside the same try as the encode, so a missing
    # credentials file marked a perfectly good video as a failed render. On a
    # checkout without GCS credentials that is every render -- docker creates
    # the absent ./cred.json as a directory, and the upload dies with
    # IsADirectoryError long after the video is safely on disk.
    try:
        upload(filename, directory=config.RENDER_DIR)
    except Exception as e:
        print('render succeeded but the automatic upload did not', renderId, e)
        return

    log.uploaded()


# --- captions ---------------------------------------------------------------

# Where projects are kept: beanie names the collection after the class.
PROJECTS = 'Project'

# Failures whose messages are already written for the person waiting, and
# need no exception name in front of them.
_SAID_PLAINLY = (
    audio_engine.AudioEngineError,
    NothingToHear,
    RefusedEdl,
    TooManyCaptions,
    # otto's refusal of a clip it cannot play (contract C8) names the clip by
    # its place in the timeline and says what is wrong with it -- written for
    # the person reading it, like the rest of this list.
    EdlException,
)


def transcription_failure(exc) -> str:
    """Why a transcription failed, as one line its owner can read."""
    if isinstance(exc, _SAID_PLAINLY):
        # Shortened, and with library paths shown as clips name them, exactly
        # as a render's reason is -- but without an exception's name in front,
        # which `failure_reason` leaves off only the refusals it knows.
        return failure_reason(RefusedEdl(str(exc)))
    return failure_reason(exc)


def captions_job(state, error=None, segments=None) -> dict:
    """A project's `captions_job` as the worker records it (contract K2)."""
    return {
        'state': state,
        'error': error,
        'engine': audio_engine.describe(),
        'segments': segments,
        'updated_at': datetime.now(timezone.utc),
    }


def record_captions_job(project_id, job, captions=None, style=None) -> None:
    fields = {'captions_job': job}
    if captions is not None:
        fields['captions'] = captions
    if style is not None:
        fields['caption_style'] = style
    get_sync_db()[PROJECTS].update_one(
        {'_id': ObjectId(str(project_id))}, {'$set': fields}
    )


class Transcriber(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Anything that escaped the task: the job failed, and says why."""
        print('failed task', task_id, exc)
        project_id = (kwargs or {}).get('projectId')
        if project_id is None:
            return
        try:
            record_captions_job(
                project_id, captions_job('failed', error=transcription_failure(exc))
            )
        except Exception as e:  # noqa: BLE001 - nothing else is left to tell
            print('could not record the failure of a transcription', project_id, e)


@renderer.task(bind=True, base=Transcriber)
def transcribeCaptions(self, projectId: str, **kwargs):
    """Caption a project's saved timeline from what it says (contract K2).

    The timeline's sound is mixed by otto, heard by the audio engine and
    turned into captions, which replace the project's own; the project's
    `captions_job` says where that has got to and, when it fails, why. The
    project id arrives as a string (contract C7). A project deleted while the
    job waited is left deleted.
    """
    projects = get_sync_db()[PROJECTS]
    project = projects.find_one(
        {'_id': ObjectId(projectId)}, {'edl': 1, 'caption_style': 1}
    )
    if project is None:
        return
    record_captions_job(projectId, captions_job('transcribing'))
    try:
        if not (project.get('edl') or {}).get('clips'):
            raise NothingToHear('the project has no saved timeline to transcribe')
        captions, heard = transcribe_timeline(project['edl'])
    except Exception as exc:  # noqa: BLE001 - every failure is the job's to report
        reason = transcription_failure(exc)
        print('could not transcribe project', projectId, reason, flush=True)
        record_captions_job(projectId, captions_job('failed', error=reason))
        return
    # Captions a project had not had: its style now says, if it did not,
    # that they are not drawn into renders until someone has looked at them.
    record_captions_job(
        projectId,
        captions_job('done', segments=heard),
        captions=[caption.dict() for caption in captions],
        style=style_to_store(None, project.get('caption_style')),
    )
