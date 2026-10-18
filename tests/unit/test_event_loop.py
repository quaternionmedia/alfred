"""Work that holds a thread is done off the event loop.

The api is one uvicorn process with one event loop. `POST /preview/` and `GET
/preview/template/{name}` were coroutines that built a clip, drew a frame and
encoded it without awaiting anything, so for as long as each took the loop ran
nothing else: every other request waited behind it, `/healthz` and `/health`
included. The editor asks for a preview on every playhead move. The captions
spec that reads `/health` while the editor previews tripped over exactly that.

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
"""

import asyncio
import threading

import httpx
import pytest

from alfred import config
from alfred.core.models.render import Render
from alfred.core.routes import preview
from alfred.main import app
from tests.unit.render_harness import OWNER, TEMPLATE_EDL, as_user, offline_documents

# The longest the stand-in for heavy work holds its thread. Reached only when
# that work runs on the event loop; otherwise the test lets it go as soon as
# /healthz has answered.
BLOCK = 10.0

BASE = 'http://alfred'


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


async def healthz_meanwhile(work, send):
    """Send a request whose work is `work`; ask for /healthz once that work has
    begun; then let it go.

    Returns /healthz's answer, whether the work was still running when that
    answer came, and the first request's own answer.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        heavy = asyncio.ensure_future(send(client))
        while not work.started.is_set() and not heavy.done():
            await asyncio.sleep(0.01)
        if not work.started.is_set():
            pytest.fail(f'the request never reached its work: {(await heavy).text}')
        health = await client.get('/healthz')
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


class TestTheApiAnswersWhile:
    def test_a_timeline_s_frame_is_made(self, signed_in, scratch, building):
        res = answers_meanwhile(
            building,
            lambda client: client.post(
                '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
            ),
        )
        assert res.status_code == 200, res.text
        assert res.json().startswith('/preview/frames/')

    def test_a_template_is_drawn(self, signed_in, scratch, building):
        res = answers_meanwhile(
            building,
            lambda client: client.get(
                '/preview/template/makeColor?color=%23f2aa4c&width=64&height=48&t=0'
            ),
        )
        assert res.status_code == 200, res.text
        assert res.headers['content-type'] == 'image/jpeg'


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
