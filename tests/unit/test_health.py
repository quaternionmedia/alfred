"""M3 -- saying whether a renderer is running.

On the thin stack, with no render worker, a queued render sat in `queued` for
ever and the editor polled it for ever. `GET /health` says how many workers
answer and how many jobs wait; `GET /healthz` answers for container health
checks with no session and no database.

The broker and the database are replaced here; the database tier asks real
ones (`integration/test_health_checks.py`).
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.routes import health
from alfred.core.utils import audio_engine, tasks
from alfred.main import app
from tests.unit.render_harness import OWNER, anonymous, as_user


class FixedRenderer:
    def __init__(self, workers=1, pending=0):
        self.state = health.RendererState(workers=workers, pending=pending)

    async def get(self):
        return self.state


class FixedAudioEngine:
    def __init__(self, configured=False, ok=False, detail='none configured'):
        self.state = audio_engine.EngineStatus(configured, ok, detail)

    async def get(self):
        return self.state


def database(up):
    async def check():
        return up

    return lambda: check


@pytest.fixture
def client():
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides + [
        health.get_renderer_state,
        health.get_database_check,
        health.get_audio_engine_state,
    ]:
        app.dependency_overrides.pop(dependency, None)


def answer(renderer=None, db_up=True, engine=None):
    app.dependency_overrides[health.get_renderer_state] = lambda: (
        renderer or FixedRenderer()
    )
    app.dependency_overrides[health.get_database_check] = database(db_up)
    app.dependency_overrides[health.get_audio_engine_state] = lambda: (
        engine or FixedAudioEngine()
    )


class TestHealthz:
    def test_answers_ok_with_no_session_and_nothing_behind_it(self, client):
        anonymous(app)
        res = client.get('/healthz')
        assert res.status_code == 200
        assert res.json() == {'ok': True}


class TestHealth:
    def test_the_contract_s_shape(self, client):
        answer(FixedRenderer(workers=2, pending=3))
        assert client.get('/health').json() == {
            'api': 'ok',
            'db': 'ok',
            'renderer': {'ok': True, 'workers': 2},
            'queue': {'pending': 3},
            'previews': {
                'running': 0,
                'waiting': 0,
                'limit': config.PREVIEW_CONCURRENCY,
            },
            'audio_engine': {
                'configured': False,
                'ok': False,
                'detail': 'none configured',
            },
        }

    def test_no_worker_is_not_ok(self, client):
        """What the thin stack answers: renders will wait for ever."""
        answer(FixedRenderer(workers=0, pending=1))
        body = client.get('/health').json()
        assert body['renderer'] == {'ok': False, 'workers': 0}
        assert body['queue'] == {'pending': 1}

    def test_a_queue_nobody_could_count_is_null(self, client):
        answer(FixedRenderer(workers=1, pending=None))
        assert client.get('/health').json()['queue'] == {'pending': None}

    def test_a_database_that_does_not_answer_is_down(self, client):
        answer(db_up=False)
        assert client.get('/health').json()['db'] == 'down'

    def test_it_needs_a_session(self, client):
        answer()
        anonymous(app)
        assert client.get('/health').status_code == 401


class TestTheAudioEngine:
    """K2: whether captions can be transcribed -- an engine configured, and
    answering -- with the reason when not."""

    def test_answering(self, client):
        answer(engine=FixedAudioEngine(configured=True, ok=True, detail=None))
        assert client.get('/health').json()['audio_engine'] == {
            'configured': True,
            'ok': True,
            'detail': None,
        }

    def test_configured_and_not_answering_says_why(self, client):
        answer(
            engine=FixedAudioEngine(
                configured=True,
                ok=False,
                detail='the audio engine at http://e: refused',
            )
        )
        body = client.get('/health').json()['audio_engine']
        assert (body['configured'], body['ok']) == (True, False)
        assert 'refused' in body['detail']

    def test_the_check_is_the_adapter_s_status(self, monkeypatch):
        monkeypatch.setattr(
            audio_engine,
            'status',
            lambda: audio_engine.EngineStatus(configured=True, ok=True),
        )
        assert health.check_audio_engine() == audio_engine.EngineStatus(True, True)

    def test_a_check_that_breaks_is_not_ok(self, monkeypatch):
        def broken():
            raise RuntimeError('vox exploded')

        monkeypatch.setattr(audio_engine, 'status', broken)
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test')
        state = health.check_audio_engine()
        assert (state.configured, state.ok) == (True, False)
        assert 'vox exploded' in state.detail

    def test_unconfigured_by_default(self, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        state = health.check_audio_engine()
        assert (state.configured, state.ok) == (False, False)
        assert 'ALFRED_AUDIO_ENGINE_URL' in state.detail

    def test_an_engine_that_hangs_is_not_ok(self, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test')

        def hang():
            import time

            time.sleep(0.5)
            return audio_engine.EngineStatus(True, True)

        cached = health.CachedRenderer(
            check=hang, ttl=60, timeout=0.05, unanswered=health.audio_engine_unanswered
        )
        state = asyncio.run(cached.get())
        assert (state.configured, state.ok) == (True, False)
        assert 'did not answer' in state.detail

    def test_it_is_asked_at_most_every_few_seconds(self):
        assert health.AUDIO_ENGINE_CACHE_SECONDS >= 5


class TestTheRendererCheck:
    def test_counts_the_workers_that_answer(self, monkeypatch):
        replies = [{'celery@a': {'ok': 'pong'}}, {'celery@b': {'ok': 'pong'}}]
        asked = []

        def ping(timeout):
            asked.append(timeout)
            return replies

        monkeypatch.setattr(tasks.renderer.control, 'ping', ping)
        assert tasks.worker_count(timeout=health.PING_TIMEOUT) == 2
        assert asked == [health.PING_TIMEOUT]

    def test_the_ping_is_short(self):
        assert health.PING_TIMEOUT <= 1

    def test_workers_poll_the_broker_well_inside_it(self):
        """A worker hears a ping when it next polls; at kombu's default of a
        second, a running worker could miss a one-second ping."""
        polling = config.CeleryConfig.broker_transport_options['polling_interval']
        assert polling <= health.PING_TIMEOUT / 2

    def test_an_unreachable_broker_is_no_workers_and_an_unknown_queue(
        self, monkeypatch
    ):
        def down(*args, **kwargs):
            raise ConnectionError('broker down')

        monkeypatch.setattr(tasks, 'worker_count', down)
        monkeypatch.setattr(tasks, 'pending_count', down)
        assert health.check_renderer() == health.RendererState(workers=0, pending=None)


class TestTheCache:
    def run(self, coroutine):
        return asyncio.run(coroutine)

    def test_an_answer_is_reused_for_a_few_seconds(self):
        calls = []

        def check():
            calls.append(1)
            return health.RendererState(workers=1, pending=0)

        cached = health.CachedRenderer(check=check, ttl=60)

        async def twice():
            await cached.get()
            await cached.get()

        self.run(twice())
        assert len(calls) == 1

    def test_and_asked_again_after(self):
        calls = []

        def check():
            calls.append(1)
            return health.RendererState(workers=len(calls), pending=0)

        cached = health.CachedRenderer(check=check, ttl=0)

        async def twice():
            first = await cached.get()
            second = await cached.get()
            return first, second

        first, second = self.run(twice())
        assert (first.workers, second.workers) == (1, 2)

    def test_concurrent_requests_share_one_check(self):
        calls = []

        def check():
            calls.append(1)
            return health.RendererState(workers=1, pending=0)

        cached = health.CachedRenderer(check=check, ttl=60)

        async def together():
            return await asyncio.gather(*(cached.get() for _ in range(5)))

        assert len(self.run(together())) == 5
        assert len(calls) == 1

    def test_a_broker_that_hangs_is_no_renderer(self, monkeypatch):
        monkeypatch.setattr(health, 'RENDERER_TIMEOUT', 0.05)

        def hang():
            import time

            time.sleep(0.5)
            return health.RendererState(workers=1, pending=0)

        cached = health.CachedRenderer(check=hang, ttl=60)
        state = self.run(cached.get())
        assert state == health.RendererState(workers=0, pending=None)


class TestTheWorkerHearsPings:
    def test_it_broadcasts_before_it_starts_consuming(self, monkeypatch):
        """kombu's MongoDB broadcast cursor is dead if it opens on nothing."""
        from celery.signals import celeryd_init

        sent = []
        monkeypatch.setattr(
            tasks.renderer.control,
            'broadcast',
            lambda command, **kwargs: sent.append((command, kwargs)),
        )
        celeryd_init.send(sender='celery@test', instance=None, conf=None, options={})
        assert sent == [('ping', {'reply': False})]

    def test_a_broker_that_is_not_there_does_not_stop_the_worker(self, monkeypatch):
        def refuse(*args, **kwargs):
            raise ConnectionError('no broker')

        monkeypatch.setattr(tasks.renderer.control, 'broadcast', refuse)
        tasks.open_the_broadcast_channel()
