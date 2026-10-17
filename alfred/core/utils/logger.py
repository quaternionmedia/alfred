from os.path import abspath

from bson import ObjectId
from proglog import ProgressBarLogger

from alfred import config

from .db import get_sync_db
from .media import RefusedEdl

# using sync db until we can write an async logger
db = get_sync_db()


def as_object_id(render_id):
    """The render's `_id` as the collection stores it.

    Task arguments are JSON now (contract C7), so the id arrives as a string,
    and a string matches no document keyed by ObjectId: progress and status
    would be written to nothing, and the render would sit at "queued" forever
    while the worker reported success.
    """
    return render_id if isinstance(render_id, ObjectId) else ObjectId(str(render_id))


# Long enough for "the file videos/x.mp4 could not be found", short enough to
# show in a list. ffmpeg's own errors run to forty lines of build flags.
REASON_LIMIT = 300


def failure_reason(exc, limit=REASON_LIMIT) -> str:
    """Why a render failed, as one short line its owner can read.

    The first line of the message only, prefixed with the exception's type
    unless it is one of ours (whose messages are already written for the
    caller). Paths inside the media library are shown as the clip named them,
    `videos/<file>`, rather than as where the worker keeps them.
    """
    lines = str(exc).strip().splitlines()
    message = lines[0].strip() if lines else ''
    if not isinstance(exc, RefusedEdl):
        message = f'{type(exc).__name__}: {message}' if message else type(exc).__name__
    library = abspath(config.VIDEO_DIR).rstrip('/') + '/'
    message = message.replace(library, 'videos/')
    if len(message) > limit:
        message = message[: limit - 3].rstrip() + '...'
    return message


def mark_failed(render_id, reason) -> None:
    """Record that a render failed, and why."""
    db.Render.update_one(
        {'_id': as_object_id(render_id)},
        {'$set': {'status': 'failed', 'error': reason}},
    )


class DbLogger(ProgressBarLogger):
    def __init__(self, task, renderId):
        super().__init__()
        self.task = task
        self.id = as_object_id(renderId)

    def callback(self, **kwargs):
        # print('task callback', kwargs)
        bar = self.state.get('bars')
        # print('bars', bar)
        if bar and bar.get('t'):
            t = bar.get('t')
            if t.get('status') == 'uploaded':
                db.Render.update_one({'_id': self.id}, {'$set': {'progress': 100}})
            elif t.get('index'):
                # print('t', t)
                p = max((100 * t['index'] / t['total']) - 1, 0)
                # print('progress', self.id, p)
                db.Render.update_one({'_id': self.id}, {'$set': {'progress': p}})

        else:
            print('got other progress message', self.state)

    def set_status(self, status):
        db.Render.update_one({'_id': self.id}, {'$set': {'status': status}})

    def rendered(self):
        """The encode finished and the file is on disk.

        Distinct from `uploaded`, which used to be the only way a render could
        be marked complete -- so a render that encoded perfectly and then
        failed to reach cloud storage was recorded as failed. With delivery a
        separate step, "the video exists" is the outcome the render task is
        responsible for.
        """
        db.Render.update_one(
            {'_id': self.id},
            {'$set': {'progress': 100, 'status': 'RENDERED', 'error': None}},
        )

    def uploaded(self):
        db.Render.update_one(
            {'_id': self.id}, {'$set': {'progress': 100, 'status': 'UPLOADED'}}
        )

    def failed(self, exc=None, reason=None, **kwargs):
        """Mark the render failed, with a short reason (contract C2).

        `reason` if given, else one derived from `exc`. It used to set the
        status alone, so the reason was printed to the worker's log and
        nowhere a person waiting on the render could see it.
        """
        if reason is None:
            reason = failure_reason(exc) if exc is not None else 'the render failed'
        print('logging failed render', self.id, reason)
        mark_failed(self.id, reason)


class CeleryLogger(ProgressBarLogger):
    def __init__(self, task):
        super(CeleryLogger, self).__init__()
        self.task = task

    def callback(self, **kwargs):
        bar = self.state['bars']
        if bar.get('t'):
            t = bar.get('t')
            if t.get('index'):
                print('progress', t)
                self.task.update_state(
                    state='PROGRESS', meta={'index': t['index'], 'total': t['total']}
                )
