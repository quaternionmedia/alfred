from proglog import ProgressBarLogger, ProgressLogger
from collections import OrderedDict
from db import db

class DbLogger(ProgressBarLogger):
    def __init__(self,
                filename=None,
                init_state=None,
                bars=None,
                ignored_bars=None,
                logged_bars='all',
                min_time_interval=0,
                ignore_bars_under=0):
        ProgressLogger.__init__(self, init_state)
        if bars is None:
            bars = OrderedDict()
        elif isinstance(bars, (list, tuple)):
            bars = OrderedDict([
                (b, dict(title=b, index=-1, total=None, message=None,
                         indent=0))
                for b in bars
            ])
        if isinstance(ignored_bars, (list, tuple)):
            ignored_bars = set(ignored_bars)
        self.ignored_bars = ignored_bars
        self.logged_bars = logged_bars
        self.state['bars'] = bars
        self.min_time_interval = min_time_interval
        self.ignore_bars_under = ignore_bars_under
        self.filename = filename
        # self.state = {}
    def callback(self, **kwargs):
        # print('db logger', kwargs, self.state['bars'])
        bar = self.state['bars']
        # print('db logger', bar, bar.keys(), bar.values())
        if bar.get('t'):
            t = bar.get('t')
            p = 100 * t['index'] / t['total']
            # print('progress', p)
            db.renders.update({'filename': self.filename}, {'$set': {'progress': p}})

from celery import Task
class celeryLogger(Task):
    def __init__(self, filename='test'):
        super().__init__(self, filename)
        self.filename=filename
    def callback(self, **kwargs):
        bar = self.state['bars']
        if bar.get('t'):
            t = bar.get('t')
            self.task.update_state(state='PROGRESS', meta={'done': t['index'], 'total': t['total']})
