"""Work that holds a thread is done off the event loop.

The api is one uvicorn process with one event loop. `POST /preview/` and `GET
/preview/template/{name}` were coroutines that built a clip, drew a frame and
encoded it without awaiting anything, and `POST /demo/media` ran ffmpeg the same
way, so for as long as each took the loop ran nothing else: every other request
waited behind it, `/healthz` and `/health` included. The editor asks for a
preview on every playhead move. The captions spec that reads `/health` while the
editor previews tripped over exactly that.

`TestTheApiAnswersWhile` shows the property itself. Each test makes the heavy
call hold its thread until the test lets it go, asks for `/healthz` meanwhile,
and requires the answer to arrive while the heavy call is still held. With the
heavy call on the event loop, the loop is what is held: `/healthz` cannot be
answered until the call gives up, BLOCK seconds later, so the test fails rather
than hangs. The app is driven in-process through httpx's ASGI transport, with
requests in flight together on one event loop, as uvicorn runs it. There is no
server and no lifespan, so no database.

`TestRunsInAThread` checks the rest one call at a time, more cheaply: the
blocking call, stood in for, records whether an event loop is running in the
thread that called it. Code a coroutine calls directly runs on the loop's
thread; the thread pool runs none.

Off the loop, requests overlap that used to run one after another.
`TestDemoMediaWhileOtherRequestsRun` holds the demo generator to what that
must not change.
"""

import asyncio
import threading
from os.path import basename
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from alfred import config
from alfred.core.models.render import Render
from alfred.core.routes import demo, preview
from alfred.core.utils.media import is_library_filename
from alfred.main import app
from tests.unit.render_harness import OWNER, TEMPLATE_EDL, as_user, offline_documents

# The longest the stand-in for heavy work holds its thread. Reached only when
# that work runs on the event loop; otherwise the test lets it go as soon as
# /healthz has answered.
BLOCK = 10.0

BASE = 'http://alfred'

DEMO_NAMES = [name for name, _ in demo.DEMO_CLIPS]


class HeavyWork:
    """Stands in for work that holds its thread: until let go, or BLOCK."""

    def __init__(self):
        self.started = threading.Event()
        self.released = threading.Event()
        self.running = False

    def hold(self):
        self.running = True
        self.started.set()
        try:
            self.released.wait(BLOCK)
        finally:
            self.running = False


def client():
    """An httpx client on the app itself, in this event loop."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


async def until(condition, timeout=BLOCK):
    """Wait, without holding the loop, until `condition()` or `timeout`."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return condition()


async def healthz_meanwhile(work, send):
    """Send a request whose work is `work`; ask for /healthz once that work has
    begun; then let it go.

    Returns /healthz's answer, whether the work was still running when that
    answer came, and the first request's own answer.
    """
    async with client() as api:
        heavy = asyncio.ensure_future(send(api))
        await until(lambda: work.started.is_set() or heavy.done())
        if not work.started.is_set():
            pytest.fail(f'the request never reached its work: {(await heavy).text}')
        health = await api.get('/healthz')
        meanwhile = work.running
        work.released.set()
        return health, meanwhile, await heavy


def answers_meanwhile(work, send):
    """`healthz_meanwhile`, checked: /healthz answered while `work` ran, and
    the request then finished. Returns the request's answer."""
    health, meanwhile, res = asyncio.run(healthz_meanwhile(work, send))
    assert health.status_code == 200 and health.json() == {'ok': True}
    assert meanwhile, (
        '/healthz was answered only once the work had finished: it ran on the '
        'event loop, and held every other request until it was done'
    )
    return res


@pytest.fixture
def signed_in(monkeypatch):
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """Where previews write, and the remote media cache they keep in check."""
    monkeypatch.setattr(config, 'PREVIEW_DIR', str(tmp_path / 'previews'))
    monkeypatch.setattr(config, 'REMOTE_CACHE_DIR', str(tmp_path / 'remote'))
    return tmp_path


class _Frame:
    """What the engine hands back, as far as a preview uses it."""

    def save_frame(self, path, t=0, withmask=False):
        with open(path, 'wb') as handle:
            handle.write(b'\xff\xd8 a frame')


@pytest.fixture
def building(monkeypatch):
    """The engine building a clip, held until the test lets it go."""
    work = HeavyWork()

    def generate(edl, moviesize=None, **kwargs):
        work.hold()
        return _Frame()

    monkeypatch.setattr(preview, 'generateEdl', generate)
    return work


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty media library for the demo generator to fill."""
    root = tmp_path / 'videos'
    monkeypatch.setattr(demo, 'VIDEO_DIR', str(root))
    return root


@pytest.fixture
def encoding(monkeypatch):
    """ffmpeg writing demo clips, held until the test lets it go. Records the
    clips it was asked for."""
    work = HeavyWork()
    work.made = []

    def generate(path, source, duration=demo.DEMO_DURATION):
        work.made.append(basename(path))
        work.hold()
        Path(path).write_bytes(b'not really a video')

    monkeypatch.setattr(demo, 'generate_clip', generate)
    return work


class TestTheApiAnswersWhile:
    def test_a_timeline_s_frame_is_made(self, signed_in, scratch, building):
        res = answers_meanwhile(
            building,
            lambda api: api.post(
                '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
            ),
        )
        assert res.status_code == 200, res.text
        assert res.json().startswith('/preview/frames/')

    def test_a_template_is_drawn(self, signed_in, scratch, building):
        res = answers_meanwhile(
            building,
            lambda api: api.get(
                '/preview/template/makeColor?color=%23f2aa4c&width=64&height=48&t=0'
            ),
        )
        assert res.status_code == 200, res.text
        assert res.headers['content-type'] == 'image/jpeg'

    def test_demo_media_is_generated(self, signed_in, library, encoding):
        res = answers_meanwhile(encoding, lambda api: api.post('/demo/media'))
        assert res.status_code == 200, res.text
        assert res.json() == {'created': DEMO_NAMES, 'skipped': []}


def on_the_loop():
    """Whether an event loop is running in the calling thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


class TestRunsInAThread:
    def test_the_preview_frame_sweep_at_startup(self, monkeypatch):
        seen = []

        def sweep(now=None, force=False):
            seen.append(on_the_loop())
            return 0

        monkeypatch.setattr(preview, 'sweep_frames', sweep)
        asyncio.run(preview.sweep_frames_at_startup())
        assert seen == [False]


class TestDemoMediaWhileOtherRequestsRun:
    def test_two_presses_at_once_make_each_clip_once(
        self, signed_in, library, encoding
    ):
        """The second waits for the first and finds its clips, as it did when
        one ran after the other on the loop."""

        async def press_twice():
            async with client() as api:
                first = asyncio.ensure_future(api.post('/demo/media'))
                await until(encoding.started.is_set)
                second = asyncio.ensure_future(api.post('/demo/media'))
                # Long enough for the second to reach the clips, were nothing
                # holding it back.
                await until(lambda: len(encoding.made) > 1, timeout=1.0)
                encoding.released.set()
                return await first, await second

        first, second = asyncio.run(press_twice())
        assert encoding.made == DEMO_NAMES
        assert first.json() == {'created': DEMO_NAMES, 'skipped': []}
        assert second.json() == {'created': [], 'skipped': DEMO_NAMES}

    def test_a_clip_is_written_out_of_sight_and_moved_into_place(
        self, library, monkeypatch
    ):
        """A listing taken while ffmpeg writes must not offer a clip that is
        half written: the library lists no hidden name."""
        library.mkdir()
        target = library / 'demo-bars.mp4'
        seen = {}

        def run(command, **kwargs):
            written = Path(command[-1])
            seen['written'] = written
            seen['in place meanwhile'] = target.exists()
            written.write_bytes(b'a whole clip')
            return SimpleNamespace(returncode=0, stderr='')

        monkeypatch.setattr(demo, 'subprocess', SimpleNamespace(run=run))
        monkeypatch.setattr(demo, 'ffmpeg_binary', lambda: 'ffmpeg')
        demo.generate_clip(str(target), 'smptebars')

        assert seen['in place meanwhile'] is False
        assert seen['written'].parent == library
        assert not is_library_filename(seen['written'].name)
        assert target.read_bytes() == b'a whole clip'
        assert [p.name for p in library.iterdir()] == ['demo-bars.mp4']

    def test_a_failed_run_leaves_nothing(self, library, monkeypatch):
        library.mkdir()
        target = library / 'demo-bars.mp4'

        def run(command, **kwargs):
            Path(command[-1]).write_bytes(b'half a clip')
            return SimpleNamespace(returncode=1, stderr='something went wrong')

        monkeypatch.setattr(demo, 'subprocess', SimpleNamespace(run=run))
        monkeypatch.setattr(demo, 'ffmpeg_binary', lambda: 'ffmpeg')
        with pytest.raises(HTTPException) as refused:
            demo.generate_clip(str(target), 'smptebars')

        assert refused.value.status_code == 500
        assert refused.value.detail == (
            f'ffmpeg could not generate {target}: something went wrong'
        )
        assert list(library.iterdir()) == []

    @pytest.mark.needs_ffmpeg
    def test_ffmpeg_writes_a_whole_clip(self, library):
        library.mkdir()
        target = library / 'demo-colour.mp4'
        demo.generate_clip(str(target), 'color=c=black:size=32x32:rate=4', duration=1)
        # An MP4 opens with its file-type box.
        assert target.read_bytes()[4:8] == b'ftyp'
        assert [p.name for p in library.iterdir()] == ['demo-colour.mp4']
