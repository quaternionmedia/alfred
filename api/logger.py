from proglog import ProgressBarLogger
from collections import OrderedDict
from db import get_sync_db
from asyncio import get_running_loop

# using sync db until we can write an async logger
db = get_sync_db()

class DbLogger(ProgressBarLogger):
    def __init__(self, task, filename):
        super().__init__()
        self.task = task
        self.filename = filename
    def callback(self, **kwargs):
        # print('task callback', kwargs)
        bar = self.state.get('bars')
        # print('bars', bar)
        if bar and bar.get('t'):
            t = bar.get('t')
            if t.get('status') == 'uploaded':
                db.renders.update_one({'filename': self.filename}, {'$set': {'progress': 100}})
            elif t.get('index'):
                # print('t', t)
                p = max((100 * t['index'] / t['total']) - 1, 0)
                # print('progress', self.filename, p)
                db.renders.update_one({'filename': self.filename}, {'$set': {'progress': p}})
            
        else:
            print('got other progress message', self.state)
    
    def set_status(self, status):
        db.renders.update_one({'filename': self.filename}, {'$set': {'status': status}})
    
    def uploaded(self):
        db.renders.update_one({'filename': self.filename}, {'$set': {'progress': 100, 'status': 'UPLOADED'}})
    
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
                self.task.update_state(state='PROGRESS', meta={'index': t['index'], 'total': t['total']})
