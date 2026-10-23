"""A clip from the media library, rendered by the worker task itself.

`test_render_pipeline.py` proves the engine encodes. Its one real encode uses a
template clip, which needs no file -- and that is why it never noticed that no
*media* clip could render through the worker. A clip dragged from the media bin
is named `videos/<file>`, the engine opened that against the worker's working
directory (/app/alfred), and every such render failed with "the file
videos/demo-bars.mp4 could not be found".

So this runs the Celery task's own code -- not `renderMultitrack` directly --
from a working directory with no `videos/` in it, on a real file in a library
directory, and checks a real video comes out. Only the database logger and the
cloud upload are replaced: everything between the task's arguments and the
encoder is the code the worker runs.
"""

import subprocess
from types import SimpleNamespace

import pytest
from proglog import ProgressBarLogger

from alfred import config

RENDER_ID = '6ad3c61e21ba2c869ca8b7ef'
OUTPUT = f'{RENDER_ID}.mp4'


def make_clip(path, seconds=1, size='160x120'):
    import imageio_ffmpeg

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-nostdin',
            '-y',
            '-loglevel',
            'error',
            '-f',
            'lavfi',
            '-i',
            f'smptebars=size={size}:rate=24:duration={seconds}',
            '-pix_fmt',
            'yuv420p',
            str(path),
        ],
        check=True,
    )


def recording_logger(events):
    """A DbLogger stand-in: a real proglog logger, recording outcomes."""

    class RecordingLogger(ProgressBarLogger):
        def __init__(self, task, render_id):
            super().__init__()
            events.append(('started', str(render_id)))

        def rendered(self):
            events.append('rendered')

        def uploaded(self):
            events.append('uploaded')

        def failed(self, *args, **kwargs):
            events.append(('failed', kwargs.get('exc')))

    return RecordingLogger


@pytest.fixture
def worker(tmp_path, monkeypatch):
    """The task module, with its library in tmp and its side effects recorded.

    The working directory is moved somewhere with no `videos/` beneath it --
    the condition the worker actually ran in.
    """
    from alfred.core.utils import tasks

    library = tmp_path / 'videos'
    library.mkdir()
    monkeypatch.setattr(config, 'VIDEO_DIR', str(library))
    monkeypatch.setattr(config, 'RENDER_DIR', str(library / 'renders'))

    elsewhere = tmp_path / 'alfred'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    events = []
    monkeypatch.setattr(tasks, 'DbLogger', recording_logger(events))
    monkeypatch.setattr(tasks, 'upload', lambda *a, **k: events.append('upload'))
    return SimpleNamespace(tasks=tasks, events=events, library=library)


def video_edl(name, seconds=1.0):
    """As the editor sends it: a dict, naming the clip as GET /videos does."""
    return {
        'clips': [
            {
                'type': 'video',
                'name': name,
                'duration': seconds,
                'start': 0.0,
                'inpoint': 0.0,
                'outpoint': seconds,
                'fadeIn': 0,
                'fadeOut': 0,
            }
        ],
        'duration': seconds,
    }


@pytest.mark.needs_ffmpeg
def test_a_library_clip_renders_to_a_playable_file(worker):
    from moviepy.video.io.VideoFileClip import VideoFileClip

    make_clip(worker.library / 'bars.mp4')

    worker.tasks.renderRemote.apply(
        kwargs=dict(
            edl=video_edl('videos/bars.mp4'),
            filename=OUTPUT,
            renderId=RENDER_ID,
            moviesize=[160, 120],
            quality='draft',
        )
    )

    assert 'rendered' in worker.events, f'the task did not finish: {worker.events}'
    out = worker.library / 'renders' / OUTPUT
    assert out.is_file() and out.stat().st_size > 0
    with VideoFileClip(str(out)) as produced:
        assert tuple(produced.size) == (160, 120)
        assert produced.duration == pytest.approx(1.0, abs=0.2)

    # Written to RENDER_DIR, so not offered back as library media.
    from alfred.core.utils.media import library_files

    assert library_files(str(worker.library)) == ['bars.mp4']


@pytest.mark.parametrize(
    'name',
    ['/etc/hostname', 'videos/../../etc/hostname', 'https://example.test/x.mp4'],
)
def test_the_worker_refuses_what_the_api_refuses(worker, monkeypatch, name):
    """The check repeats in the worker, before the engine sees anything.

    The api refuses these at the request; the worker's own check covers EDLs
    stored before that existed and re-queued. Without it, an absolute name
    had the worker open `/etc/hostname`.
    """
    called = []
    monkeypatch.setattr(
        worker.tasks, 'renderMultitrack', lambda **kw: called.append(kw)
    )

    worker.tasks.renderRemote.apply(
        kwargs=dict(edl=video_edl(name), filename=OUTPUT, renderId=RENDER_ID)
    )

    assert called == [], 'the engine was handed a name the worker should refuse'
    failures = [e for e in worker.events if isinstance(e, tuple) and e[0] == 'failed']
    assert failures, f'the refusal was not recorded: {worker.events}'


@pytest.mark.parametrize(
    'audio',
    ['/etc/hostname', 'videos/../../etc/hostname', 'https://example.test/x.mp3'],
)
def test_the_worker_refuses_a_soundtrack_the_api_would_refuse(
    worker, monkeypatch, audio
):
    """The engine honours a soundtrack now -- it used to drop the argument --
    and opens or fetches it as it would a clip's name."""
    (worker.library / 'bars.mp4').write_bytes(b'only its name is checked')
    called = []
    monkeypatch.setattr(
        worker.tasks, 'renderMultitrack', lambda **kw: called.append(kw)
    )

    worker.tasks.renderRemote.apply(
        kwargs=dict(
            edl=video_edl('videos/bars.mp4'),
            filename=OUTPUT,
            renderId=RENDER_ID,
            audio=audio,
        )
    )

    assert called == [], 'the engine was handed a soundtrack it should not open'
    failures = [e for e in worker.events if isinstance(e, tuple) and e[0] == 'failed']
    assert failures and 'soundtrack' in str(failures[0][1])


def test_a_library_soundtrack_reaches_the_engine_resolved(worker, monkeypatch):
    for name in ('bars.mp4', 'music.mp3'):
        (worker.library / name).write_bytes(b'only its name is checked')
    called = []
    monkeypatch.setattr(
        worker.tasks, 'renderMultitrack', lambda **kw: called.append(kw)
    )

    worker.tasks.renderRemote.apply(
        kwargs=dict(
            edl=video_edl('videos/bars.mp4'),
            filename=OUTPUT,
            renderId=RENDER_ID,
            audio='videos/music.mp3',
        )
    )

    (call,) = called
    assert call['audio'] == str(worker.library / 'music.mp3')


@pytest.mark.parametrize(
    'filename', ['../../escape.mp4', '/tmp/escape.mp4', 'name.mp4', 'x/../y.mp4']
)
def test_the_worker_writes_only_to_an_id_derived_name(worker, monkeypatch, filename):
    """A stored render's filename was built from its request and could hold `../`.

    The api names output `<id>.mp4` now; the worker refuses anything else, so a
    re-queued old render cannot write outside the output directory.
    """
    called = []
    monkeypatch.setattr(
        worker.tasks, 'renderMultitrack', lambda **kw: called.append(kw)
    )

    worker.tasks.renderRemote.apply(
        kwargs=dict(
            edl=video_edl('videos/bars.mp4'), filename=filename, renderId=RENDER_ID
        )
    )

    assert called == []
    assert any(isinstance(e, tuple) and e[0] == 'failed' for e in worker.events)
