from bson import ObjectId
from proglog import ProgressBarLogger

from .db import get_sync_db

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
            {'_id': self.id}, {'$set': {'progress': 100, 'status': 'RENDERED'}}
        )

    def uploaded(self):
        db.Render.update_one(
            {'_id': self.id}, {'$set': {'progress': 100, 'status': 'UPLOADED'}}
        )

    def failed(self, *args, **kwargs):
        print('logging failed render', args, kwargs)
        self.set_status('failed')


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
