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
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
from otto.exceptions import FFmpegException

from alfred import config
from alfred.core.models.render import Render
from alfred.core.routes import demo, preview
from alfred.core.utils.media import is_library_filename
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    TEMPLATE_EDL,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    render_request,
    use_fakes,
)

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


@pytest.fixture
def building(monkeypatch):
    """The engine drawing a frame, held until the test lets it go."""
    work = HeavyWork()

    def draw(edl, t, filename, moviesize=None):
        work.hold()
        with open(filename, 'wb') as handle:
            handle.write(b'\xff\xd8 a frame')
        return filename

    monkeypatch.setattr(preview, 'renderFrame', draw)
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


class SendsFrom(FakeQueue):
    """A queue that records, for each send, whether it ran on the event loop."""

    def __init__(self):
        super().__init__()
        self.on_the_loop = []

    def __call__(self, **kwargs):
        self.on_the_loop.append(on_the_loop())
        super().__call__(**kwargs)


@pytest.fixture
def renders(signed_in):
    """The render routes on an in-memory store and a queue that says where
    each send ran."""
    store, queue = FakeRenderStore(), SendsFrom()
    overrides = use_fakes(app, store, queue)
    yield store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class OneProject:
    """The captions routes' store, holding one project."""

    def __init__(self, document):
        self.document = document

    async def find(self, query):
        if query['_id'] != self.document['_id']:
            return None
        return dict(self.document)

    async def set(self, project_id, fields):
        self.document.update(fields)

    async def claim(self, project_id, job, stale_before):
        return True


@pytest.fixture
def transcribable(signed_in, tmp_path, monkeypatch):
    """A project of OWNER's with something to hear, an engine to hear it,
    and a queue that says where each send ran."""
    from alfred.core.routes import captions
    from alfred.core.utils import audio_engine

    (tmp_path / 'talk.mp4').write_bytes(b'not really a video')
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')
    monkeypatch.setattr(audio_engine, 'problem', lambda: None)
    clip = {'type': 'video', 'name': 'videos/talk.mp4', 'duration': 4, 'start': 0}
    project = {'_id': ObjectId(), 'owner': OWNER.email, 'edl': {'clips': [clip]}}
    queue = SendsFrom()
    app.dependency_overrides[captions.get_captions_store] = lambda: OneProject(project)
    app.dependency_overrides[captions.get_captions_queue] = lambda: queue
    yield project, queue
    for dependency in (captions.get_captions_store, captions.get_captions_queue):
        app.dependency_overrides.pop(dependency, None)


class TestRunsInAThread:
    def test_the_preview_frame_sweep_at_startup(self, monkeypatch):
        seen = []

        def sweep(now=None, force=False):
            seen.append(on_the_loop())
            return 0

        monkeypatch.setattr(preview, 'sweep_frames', sweep)
        asyncio.run(preview.sweep_frames_at_startup())
        assert seen == [False]

    def test_the_font_probe_at_startup(self, monkeypatch):
        from alfred import main

        seen, written = [], []

        def fc_list(command, capture_output=False):
            seen.append(on_the_loop())
            return SimpleNamespace(stdout=b'"DejaVu Sans-Book"\n')

        class Fonts:
            async def update_one(self, query, update, upsert=False):
                written.append((query, update))

            async def delete_many(self, query):
                written.append((query,))

        monkeypatch.setattr(main, 'bash', fc_list)
        monkeypatch.setattr(main, 'get_db', lambda: SimpleNamespace(fonts=Fonts()))
        asyncio.run(main.checkFonts())
        assert seen == [False]
        assert written == [
            ({'family': 'DejaVu-Sans'}, {'$set': {'style': ['Book']}}),
            ({'family': {'$nin': ['DejaVu-Sans']}},),
        ]

    def test_sending_a_render_to_the_worker(self, renders):
        _, queue = renders
        res = TestClient(app).post('/render', json=render_request())
        assert res.status_code == 200, res.text
        assert queue.on_the_loop == [False]

    def test_sending_one_again(self, renders):
        store, queue = renders
        render = make_render(username=OWNER.email)
        store.renders[render.id] = render
        res = TestClient(app).post(f'/render/rerender/{render.id}')
        assert res.status_code == 200, res.text
        assert queue.on_the_loop == [False]

    def test_sending_a_transcription_to_the_worker(self, transcribable):
        project, queue = transcribable
        res = TestClient(app).post(f'/project/{project["_id"]}/captions/transcribe')
        assert res.status_code == 202, res.text
        assert queue.on_the_loop == [False]

    def test_listing_the_library(self, signed_in, tmp_path, monkeypatch):
        from alfred.core.routes import video

        seen = []

        def listing(root):
            seen.append(on_the_loop())
            return ['clip.mp4']

        monkeypatch.setattr(video, 'VIDEO_DIR', str(tmp_path))
        monkeypatch.setattr(video, 'library_files', listing)
        res = TestClient(app).get('/videos')
        assert res.status_code == 200, res.text
        assert res.json() == ['videos/clip.mp4']
        assert seen == [False]

    def test_reading_a_subtitle_file(self, transcribable, monkeypatch):
        from alfred.core.routes import captions

        project, _ = transcribable
        seen = []
        real = captions.parse

        def parse(format, text):
            seen.append(on_the_loop())
            return real(format, text)

        monkeypatch.setattr(captions, 'parse', parse)
        res = TestClient(app).post(
            f'/project/{project["_id"]}/captions/import',
            json={'format': 'srt', 'text': '1\n00:00:01,000 --> 00:00:02,500\nHello\n'},
        )
        assert res.status_code == 200, res.text
        assert res.json()['captions'] == [{'start': 1.0, 'end': 2.5, 'text': 'Hello'}]
        assert seen == [False]

    def test_queueing_the_mail_about_an_issue_with_a_render(self, renders, monkeypatch):
        from alfred.core.utils import support_mail

        store, _ = renders
        render = make_render(username=OWNER.email)
        store.renders[render.id] = render
        queue = SendsFrom()
        monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: True)
        app.dependency_overrides[support_mail.get_mail_queue] = lambda: queue
        try:
            res = TestClient(app).post(
                f'/render/{render.id}/report', json='it went dark'
            )
        finally:
            app.dependency_overrides.pop(support_mail.get_mail_queue, None)
        assert res.status_code == 202, res.text
        assert queue.on_the_loop == [False]

    def test_making_an_invoice_and_queueing_its_mail(self, monkeypatch):
        from alfred.core.routes import admin
        from alfred.core.utils import support_mail

        seen = []

        def generate(client, start, end):
            seen.append(('invoice', on_the_loop()))
            return []

        def queue(**job):
            seen.append(('mail', on_the_loop()))

        monkeypatch.setattr(admin, 'generate_invoice', generate)
        monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: True)
        app.dependency_overrides[support_mail.get_mail_queue] = lambda: queue
        overrides = as_user(app, ADMIN)
        try:
            res = TestClient(app).post(
                '/invoice?client=c@example.com&startDate=2026-09-01&endDate=2026-10-01'
            )
        finally:
            for dependency in overrides + [support_mail.get_mail_queue]:
                app.dependency_overrides.pop(dependency, None)
        assert res.status_code == 202, res.text
        assert seen == [('invoice', False), ('mail', False)]


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
        """A listing taken while the engine writes must not offer a clip that
        is half written: the library lists no hidden name."""
        library.mkdir()
        target = library / 'demo-bars.mp4'
        seen = {}

        def make(filename, source, duration=None):
            written = Path(filename)
            seen['written'], seen['source'] = written, source
            seen['in place meanwhile'] = target.exists()
            written.write_bytes(b'a whole clip')
            return filename

        monkeypatch.setattr(demo, 'demoClip', make)
        demo.generate_clip(str(target), 'bars')

        assert seen['source'] == 'bars'
        assert seen['in place meanwhile'] is False
        assert seen['written'].parent == library
        assert not is_library_filename(seen['written'].name)
        assert target.read_bytes() == b'a whole clip'
        assert [p.name for p in library.iterdir()] == ['demo-bars.mp4']

    def test_a_failed_run_leaves_nothing(self, library, monkeypatch):
        library.mkdir()
        target = library / 'demo-bars.mp4'

        def make(filename, source, duration=None):
            Path(filename).write_bytes(b'half a clip')
            raise FFmpegException(
                'ffmpeg could not write a demo clip', stderr='something went wrong'
            )

        monkeypatch.setattr(demo, 'demoClip', make)
        with pytest.raises(HTTPException) as refused:
            demo.generate_clip(str(target), 'bars')

        assert refused.value.status_code == 500
        assert refused.value.detail == (
            f'ffmpeg could not generate {target}: something went wrong'
        )
        assert list(library.iterdir()) == []

    def test_only_the_end_of_what_ffmpeg_said_is_shown(self, library, monkeypatch):
        library.mkdir()
        said = 'banner ' * 200 + 'the reason'

        def make(filename, source, duration=None):
            raise FFmpegException('ffmpeg could not write a demo clip', stderr=said)

        monkeypatch.setattr(demo, 'demoClip', make)
        with pytest.raises(HTTPException) as refused:
            demo.generate_clip(str(library / 'demo-bars.mp4'), 'bars')

        assert refused.value.detail.endswith(said[-400:])
        assert 'banner ' * 60 not in refused.value.detail

    def test_no_ffmpeg_to_start_is_a_503(self, library, monkeypatch):
        library.mkdir()

        def make(filename, source, duration=None):
            raise FileNotFoundError(2, 'No such file or directory', '/no/ffmpeg')

        monkeypatch.setattr(demo, 'demoClip', make)
        with pytest.raises(HTTPException) as refused:
            demo.generate_clip(str(library / 'demo-bars.mp4'), 'bars')

        assert refused.value.status_code == 503
        assert refused.value.detail.startswith(
            'no ffmpeg available to generate demo media: '
        )
        assert list(library.iterdir()) == []

    @pytest.mark.needs_ffmpeg
    def test_the_engine_writes_a_whole_clip(self, library):
        library.mkdir()
        target = library / 'demo-colour.mp4'
        demo.generate_clip(str(target), 'color', duration=1)
        # An MP4 opens with its file-type box.
        assert target.read_bytes()[4:8] == b'ftyp'
        assert [p.name for p in library.iterdir()] == ['demo-colour.mp4']

    def test_every_demo_clip_names_a_picture_the_engine_has(self):
        from otto.demo import DEMO_SOURCES

        assert {source for _, source in demo.DEMO_CLIPS} <= set(DEMO_SOURCES)
