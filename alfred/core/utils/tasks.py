from base64 import b64decode
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
from .captions import TooManyCaptions, TooManyWords, style_to_store
from .db import get_sync_db
from .email import mail_failure, send_mail, transient
from .encoding import preset_for
from .logger import DbLogger, failure_reason, mark_failed
from .media import MediaNameError, RefusedEdl, check_media_name, resolve_edl
from .storage import sweep_remote_cache_now_and_then
from .transcription import NothingToHear, transcribe_timeline

renderer = Celery(
    'renderer',
    backend=config.CELERY_BACKEND,
    broker=config.CELERY_BROKER,
    # By package name only: a second name registers every task twice.
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
    """Broadcast a ping nobody waits for, so this worker hears broadcasts.

    On a MongoDB broker a worker hears them (`/health`'s ping among them)
    through a tailable cursor, which MongoDB kills at once on an empty
    collection and kombu never reopens: the first worker on a fresh database
    would answer no ping. A failure here leaves the worker running, deaf.
    """
    try:
        renderer.control.broadcast('ping', reply=False)
    except Exception as exc:  # noqa: BLE001 - the worker must start regardless
        print('could not open the broadcast channel; pings may go unheard', exc)


class Renderer(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Anything that escaped the task: record it on this job's render, the
        one in its arguments (the task object is shared by every job)."""
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

    Arguments arrive as JSON (contract C7). Encoding is the preset `quality`
    names (C5); a `bitrate` or `ffmpeg_params` in `kwargs` is ignored.
    """
    # A local, not `self.log`: the task object outlives the job.
    log = DbLogger(self, renderId)
    try:
        # Only a name `output_filename` makes: checked here too, for jobs
        # built elsewhere.
        if not is_output_filename(filename):
            raise ValueError(f'refusing to write a render to {filename!r}')
        # Resolved against VIDEO_DIR, not the working directory, and checked
        # again for stored EDLs the api's check predates.
        timeline = resolve_edl(Edl.model_validate(edl))
        # A soundtrack is media too, held to the same rule. The api never sets it.
        soundtrack = None
        if audio is not None:
            try:
                soundtrack = check_media_name(audio)
            except MediaNameError as exc:
                raise MediaNameError(f'soundtrack: {exc}') from exc
        # RENDER_DIR, which no library route lists or serves.
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

    # Finished, whatever happens to the upload.
    log.rendered()

    # The worker fetches most remote media, so it sweeps the cache too.
    try:
        sweep_remote_cache_now_and_then()
    except Exception as e:  # noqa: BLE001 - housekeeping must not fail a render
        print('could not sweep the remote media cache', e)

    # The automatic bucket upload, best effort: without credentials (Docker
    # makes a missing ./cred.json a directory) it fails, and the render stands.
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
    TooManyWords,
    # otto's refusal of an unplayable clip (C8), which names the clip.
    EdlException,
)


def transcription_failure(exc) -> str:
    """Why a transcription failed, as one line its owner can read."""
    if isinstance(exc, _SAID_PLAINLY):
        # As a render's reason, without an exception's name in front.
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


def record_captions_job(project_id, job, captions=None, style=None, words=None) -> None:
    fields = {'captions_job': job}
    if captions is not None:
        fields['captions'] = captions
    if style is not None:
        fields['caption_style'] = style
    if words is not None:
        fields['words'] = words
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
    turned into captions, which replace the project's own, with its `words`;
    the project's `captions_job` says where that has got to and, when it
    fails, why (captions and words left as they were). The project id arrives
    as a string (contract C7). A project deleted while the job waited is left
    deleted.
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
        captions, heard, words = transcribe_timeline(project['edl'])
    except Exception as exc:  # noqa: BLE001 - every failure is the job's to report
        reason = transcription_failure(exc)
        print('could not transcribe project', projectId, reason, flush=True)
        record_captions_job(projectId, captions_job('failed', error=reason))
        return
    # New captions are not drawn into renders until someone has looked.
    record_captions_job(
        projectId,
        captions_job('done', segments=heard),
        captions=[caption.model_dump() for caption in captions],
        style=style_to_store(None, project.get('caption_style')),
        words=[word.model_dump() for word in words],
    )


# --- mail -------------------------------------------------------------------

# Retries of a mail that may yet pass, and the first wait in seconds, doubling:
# 30 s to 8 minutes, the last try about a quarter of an hour after the first.
MAIL_RETRIES = 5
MAIL_FIRST_WAIT = 30


def mail_wait(tries) -> int:
    """Seconds to wait before trying a mail again, when it has been tried
    again `tries` times already."""
    return MAIL_FIRST_WAIT * 2**tries


class MailNotSent(Exception):
    """Why a mail was not sent, said without the mail or an address."""


@renderer.task(bind=True, max_retries=MAIL_RETRIES)
def mailSupport(self, about, subject, message, attachments=None, **kwargs):
    """Mail support -- EMAIL_SENDTO -- `message` under `subject`.

    Queued by the issue-report and invoice routes (`utils.support_mail`), with
    each attachment as `{filename, content}`, its bytes in base64 (contract
    C7). Sent with ALFRED_SMTP_TIMEOUT on every step. A failure that may pass
    -- no answer, a dropped connection, a reply in the 400s -- is tried again
    MAIL_RETRIES times, waiting longer each time (`mail_wait`); anything else
    fails the job at once.

    The log says what happened to the mail named by `about` and why, and
    nothing of the mail itself: no text, no subject, no address.
    """
    files = [(a['filename'], b64decode(a['content'])) for a in attachments or []]
    try:
        send_mail(
            config.EMAIL_SENDTO,
            subject,
            message,
            attachments=files,
            timeout=config.SMTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 - every failure is said as one line
        reason, again = mail_failure(exc), transient(exc)
    else:
        print(f'mailed {about}', flush=True)
        return 'sent'
    # Outside the `except`, so smtplib's exception, which can carry addresses,
    # is not chained into Celery's log.
    tries = self.request.retries
    if again and tries < MAIL_RETRIES:
        wait = mail_wait(tries)
        print(
            f'could not mail {about} ({reason}); trying again in {wait} s', flush=True
        )
        raise self.retry(exc=MailNotSent(reason), countdown=wait)
    tried = f'after {tries + 1} tries' if tries else 'and will not try again'
    raise MailNotSent(f'could not mail {about} {tried}: {reason}')
