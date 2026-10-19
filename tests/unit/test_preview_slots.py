"""A cap on how many previews the api draws at once.

Previews ran in the thread pool with nothing to say how many: the pool is
AnyIO's forty threads, shared with file responses, every other route's
offloaded work and `/health`'s broker ping, and the editor asks for a preview
on every playhead move. Now each preview takes one of
ALFRED_PREVIEW_CONCURRENCY slots first (`utils.concurrency`). The rest wait
their turn on the event loop, holding no thread, for at most
ALFRED_PREVIEW_WAIT seconds, and are then answered 503 with Retry-After.
`GET /health` says how the slots are used.

The slots are tested on their own, then around a small route of the test's
own, and then on the two real preview routes -- with the slots taken by the
test, so what those routes draw with does not matter here.
"""

import asyncio
import os
import threading

import anyio.to_thread
import httpx
import pytest
from fastapi import FastAPI, HTTPException

from alfred import config
from alfred.config import resolve_count
from alfred.core.models.render import Render
from alfred.core.routes import health, preview
from alfred.core.utils import concurrency
from alfred.core.utils.concurrency import RETRY_AFTER, Busy, Slots, preview_slot
from alfred.main import app
from tests.unit.render_harness import OWNER, TEMPLATE_EDL, as_user, offline_documents

BASE = 'http://alfred'

# The longest anything here waits for something that should have happened.
PATIENCE = 10.0


async def until(condition, timeout=PATIENCE):
    """Wait, without holding the loop, until `condition()` or `timeout`."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return condition()


def slots(limit=1, wait=1.0):
    return Slots(limit=lambda: limit, wait=lambda: wait)


class TestTheSetting:
    def test_unset_or_empty_is_the_default(self):
        assert resolve_count({}, 'X', 4) == 4
        assert resolve_count({'X': ''}, 'X', 4) == 4
        assert resolve_count({'X': '  '}, 'X', 4) == 4

    def test_a_whole_number_is_taken(self):
        assert resolve_count({'X': '8'}, 'X', 4) == 8
        assert resolve_count({'X': ' 1 '}, 'X', 4) == 1

    @pytest.mark.parametrize('value', ['four', '1.5', '0', '-2'])
    def test_anything_else_is_the_default_and_says_so(self, value, capsys):
        assert resolve_count({'X': value}, 'X', 4) == 4
        assert 'X=' in capsys.readouterr().err

    @pytest.mark.parametrize(
        'name,setting,default',
        [
            ('ALFRED_PREVIEW_CONCURRENCY', 'PREVIEW_CONCURRENCY', 4),
            ('ALFRED_PREVIEW_WAIT', 'PREVIEW_WAIT', 10),
        ],
    )
    def test_the_defaults(self, name, setting, default):
        if os.environ.get(name):
            pytest.skip(f'{name} is set for this run')
        assert getattr(config, setting) == default

    def test_the_previews_read_them(self, monkeypatch):
        monkeypatch.setattr(config, 'PREVIEW_CONCURRENCY', 7)
        monkeypatch.setattr(config, 'PREVIEW_WAIT', 3)
        assert concurrency.previews.limit() == 7
        assert concurrency.previews.wait() == 3


class TestSlots:
    def test_up_to_the_limit_at_once(self):
        async def run():
            cap = slots(limit=2)
            await cap.acquire()
            await cap.acquire()
            return cap.use()

        assert asyncio.run(run()) == concurrency.Use(running=2, waiting=0, limit=2)

    def test_the_next_waits_for_a_slot_and_gets_the_one_given_back(self):
        async def run():
            cap = slots(limit=1, wait=PATIENCE)
            await cap.acquire()
            second = asyncio.ensure_future(cap.acquire())
            await until(lambda: cap.use().waiting == 1)
            waiting = second.done(), cap.use()
            cap.release()
            await second
            return waiting, cap.use()

        (done, meanwhile), after = asyncio.run(run())
        assert not done
        assert meanwhile == concurrency.Use(running=1, waiting=1, limit=1)
        assert after == concurrency.Use(running=1, waiting=0, limit=1)

    def test_those_waiting_are_let_in_the_order_they_came(self):
        async def run():
            cap = slots(limit=1, wait=PATIENCE)
            order = []

            async def take(name):
                await cap.acquire()
                order.append(name)

            await cap.acquire()
            waiting = []
            for name in 'abc':
                waiting.append(asyncio.ensure_future(take(name)))
                await until(lambda: cap.use().waiting == len(waiting))
            for _ in 'abc':
                cap.release()
                await until(lambda: len(order) == 3 - cap.use().waiting)
            await asyncio.gather(*waiting)
            return order

        assert asyncio.run(run()) == ['a', 'b', 'c']

    def test_one_that_waits_too_long_is_busy_and_leaves_the_line(self):
        async def run():
            cap = slots(limit=1, wait=0.05)
            await cap.acquire()
            with pytest.raises(Busy):
                await cap.acquire()
            return cap.use()

        assert asyncio.run(run()) == concurrency.Use(running=1, waiting=0, limit=1)

    def test_one_that_goes_away_while_waiting_leaves_the_line(self):
        async def run():
            cap = slots(limit=1, wait=PATIENCE)
            await cap.acquire()
            gone = asyncio.ensure_future(cap.acquire())
            await until(lambda: cap.use().waiting == 1)
            gone.cancel()
            with pytest.raises(asyncio.CancelledError):
                await gone
            meanwhile = cap.use()
            cap.release()
            return meanwhile, cap.use()

        meanwhile, after = asyncio.run(run())
        assert meanwhile == concurrency.Use(running=1, waiting=0, limit=1)
        assert after == concurrency.Use(running=0, waiting=0, limit=1)

    def test_a_slot_given_to_one_that_has_just_gone_is_passed_on(self):
        """The slot came and the request went in the same moment: the slot
        is not lost with it."""

        async def run():
            cap = slots(limit=1, wait=PATIENCE)
            await cap.acquire()
            gone = asyncio.ensure_future(cap.acquire())
            await until(lambda: cap.use().waiting == 1)
            nxt = asyncio.ensure_future(cap.acquire())
            await until(lambda: cap.use().waiting == 2)
            # Released, so the first in line holds the slot -- and cancelled
            # before it has run again to see that.
            cap.release()
            gone.cancel()
            with pytest.raises(asyncio.CancelledError):
                await gone
            await asyncio.wait_for(nxt, PATIENCE)
            return cap.use()

        assert asyncio.run(run()) == concurrency.Use(running=1, waiting=0, limit=1)

    def test_a_limit_raised_lets_more_in(self):
        async def run():
            limit = [1]
            cap = Slots(limit=lambda: limit[0], wait=lambda: PATIENCE)
            await cap.acquire()
            limit[0] = 2
            await asyncio.wait_for(cap.acquire(), 1)
            return cap.use()

        assert asyncio.run(run()) == concurrency.Use(running=2, waiting=0, limit=2)


# --- around a route --------------------------------------------------------


class Held:
    """Work that holds its thread until the test lets it go."""

    def __init__(self):
        self.started = threading.Semaphore(0)
        self.released = threading.Event()
        self.threads = []

    def hold(self):
        self.threads.append(threading.current_thread() is threading.main_thread())
        self.started.release()
        self.released.wait(PATIENCE)


@pytest.fixture
def cap(monkeypatch):
    """The preview slots, one at a time, and a short wait."""
    monkeypatch.setattr(config, 'PREVIEW_CONCURRENCY', 1)
    monkeypatch.setattr(config, 'PREVIEW_WAIT', 1)
    assert concurrency.previews.use().running == 0, 'a slot was left taken'
    yield concurrency.previews
    assert concurrency.previews.use() == concurrency.Use(
        0, 0, 1
    ), 'a slot was left taken, or a request left waiting'


@pytest.fixture
def drawing():
    """A small app with one route behind `preview_slot`."""
    held = Held()
    small = FastAPI()

    @small.get('/draw')
    @preview_slot
    def draw(n: int = 0):
        """# Draw

        Draws `n`."""
        if n < 0:
            raise HTTPException(status_code=422, detail='n must not be negative')
        on_the_loop = True
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_the_loop = False
        held.hold()
        return {'n': n, 'on_the_loop': on_the_loop}

    return small, held


def on(application):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url=BASE
    )


class TestARouteBehindASlot:
    def test_is_drawn_in_the_thread_pool_and_answers_as_before(self, cap, drawing):
        small, held = drawing
        held.released.set()

        async def run():
            async with on(small) as api:
                return await api.get('/draw?n=3')

        res = asyncio.run(run())
        assert res.status_code == 200, res.text
        assert res.json() == {'n': 3, 'on_the_loop': False}

    def test_keeps_its_parameters_name_and_documentation(self, drawing):
        small, _ = drawing
        operation = small.openapi()['paths']['/draw']['get']
        assert [p['name'] for p in operation['parameters']] == ['n']
        assert operation['operationId'].startswith('draw')
        assert 'Draws `n`.' in operation['description']

    def test_a_second_waits_for_the_first_and_is_then_drawn(self, cap, drawing):
        small, held = drawing

        async def run():
            async with on(small) as api:
                first = asyncio.ensure_future(api.get('/draw?n=1'))
                await until(lambda: cap.use().running == 1)
                second = asyncio.ensure_future(api.get('/draw?n=2'))
                await until(lambda: cap.use().waiting == 1)
                meanwhile = cap.use(), len(held.threads)
                held.released.set()
                return meanwhile, await first, await second

        (use, drawn), first, second = asyncio.run(run())
        assert use == concurrency.Use(running=1, waiting=1, limit=1)
        assert drawn == 1, 'the second was drawn before the first gave its slot back'
        assert (first.status_code, second.status_code) == (200, 200)
        assert second.json()['n'] == 2

    def test_one_that_finds_no_slot_in_time_is_a_503_with_retry_after(
        self, cap, drawing
    ):
        small, held = drawing

        async def run():
            async with on(small) as api:
                first = asyncio.ensure_future(api.get('/draw?n=1'))
                await until(lambda: cap.use().running == 1)
                turned_away = await api.get('/draw?n=2')
                held.released.set()
                return await first, turned_away

        first, turned_away = asyncio.run(run())
        assert first.status_code == 200
        assert turned_away.status_code == 503
        assert turned_away.headers['retry-after'] == str(RETRY_AFTER)
        detail = turned_away.json()['detail']
        assert 'previews' in detail and f'{RETRY_AFTER} seconds' in detail
        assert len(held.threads) == 1, 'the one turned away was drawn anyway'

    def test_a_refusal_gives_the_slot_back(self, cap, drawing):
        small, _ = drawing

        async def run():
            async with on(small) as api:
                return await api.get('/draw?n=-1')

        assert asyncio.run(run()).status_code == 422
        # The fixture checks the slot is free again.

    def test_those_waiting_hold_no_thread(self, cap, drawing):
        """The point of waiting on the loop: five previews waiting borrow
        nothing from the thread pool; only the one being drawn does."""
        small, held = drawing

        async def run():
            limiter = anyio.to_thread.current_default_thread_limiter()
            async with on(small) as api:
                first = asyncio.ensure_future(api.get('/draw?n=0'))
                await until(lambda: cap.use().running == 1)
                rest = [
                    asyncio.ensure_future(api.get(f'/draw?n={n}')) for n in range(5)
                ]
                await until(lambda: cap.use().waiting == 5)
                borrowed = limiter.borrowed_tokens
                held.released.set()
                await first
                await asyncio.gather(*rest)
                return borrowed

        assert asyncio.run(run()) == 1


# --- the preview routes ----------------------------------------------------


@pytest.fixture
def signed_in(monkeypatch):
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def preview_requests():
    """The two kinds of preview, each as a request on `api`."""
    return {
        'a timeline frame': lambda api: api.post(
            '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
        ),
        'a template frame': lambda api: api.get(
            '/preview/template/makeColor?color=%23f2aa4c&width=64&height=48&t=0'
        ),
    }


class TestThePreviewRoutes:
    def test_both_are_behind_the_slots(self):
        assert preview.previewFrame.__wrapped__.__name__ == 'previewFrame'
        assert preview.previewTemplate.__wrapped__.__name__ == 'previewTemplate'
        assert asyncio.iscoroutinefunction(preview.previewFrame)
        assert asyncio.iscoroutinefunction(preview.previewTemplate)

    def test_they_keep_their_parameters_and_document_the_503(self):
        paths = app.openapi()['paths']
        template = paths['/preview/template/{name}']['get']
        assert {'name', 'width', 'height', 't', 'length'} <= {
            p['name'] for p in template['parameters']
        }
        frame = paths['/preview/']['post']
        assert 't' in [p['name'] for p in frame['parameters']]
        assert 'requestBody' in frame
        for operation in (template, frame):
            assert '503' in operation['responses']

    @pytest.mark.parametrize('kind', preview_requests())
    def test_with_every_slot_taken_one_waits_and_is_turned_away(
        self, signed_in, cap, kind
    ):
        """And while it waits, `/health` says so."""
        send = preview_requests()[kind]
        answer_health()

        async def run():
            await cap.acquire()
            try:
                async with on(app) as api:
                    waiting = asyncio.ensure_future(send(api))
                    await until(lambda: cap.use().waiting == 1 or waiting.done())
                    report = await api.get('/health')
                    return report, await waiting
            finally:
                cap.release()

        try:
            report, res = asyncio.run(run())
        finally:
            forget_health()
        assert report.json()['previews'] == {'running': 1, 'waiting': 1, 'limit': 1}
        assert res.status_code == 503, res.text
        assert res.headers['retry-after'] == str(RETRY_AFTER)

    def test_a_slot_given_back_in_time_lets_it_through(self, signed_in, cap):
        """Through to the route itself, which answers for a template it does
        not offer as it always has."""

        async def run():
            await cap.acquire()
            released = False
            try:
                async with on(app) as api:
                    waiting = asyncio.ensure_future(
                        api.get('/preview/template/notATemplate?width=64&height=48')
                    )
                    await until(lambda: cap.use().waiting == 1)
                    cap.release()
                    released = True
                    return await waiting
            finally:
                if not released:
                    cap.release()

        res = asyncio.run(run())
        assert res.status_code == 404, res.text
        assert res.json() == {'detail': 'No such template: notATemplate'}

    def test_the_frames_themselves_are_not_behind_the_slots(self, signed_in, cap):
        """Fetching a frame already drawn is a file response, not a preview."""

        async def run():
            await cap.acquire()
            try:
                async with on(app) as api:
                    return await asyncio.wait_for(
                        api.get('/preview/frames/' + '0' * 32 + '.jpg'), PATIENCE
                    )
            finally:
                cap.release()

        assert asyncio.run(run()).status_code == 404


# --- /health ----------------------------------------------------------------


class FixedRenderer:
    async def get(self):
        return health.RendererState(workers=1, pending=0)


class FixedAudioEngine:
    async def get(self):
        from alfred.core.utils import audio_engine

        return audio_engine.EngineStatus(False, False, 'none configured')


def database_up():
    async def check():
        return True

    return check


def answer_health():
    app.dependency_overrides[health.get_renderer_state] = FixedRenderer
    app.dependency_overrides[health.get_database_check] = database_up
    app.dependency_overrides[health.get_audio_engine_state] = FixedAudioEngine


def forget_health():
    for dependency in (
        health.get_renderer_state,
        health.get_database_check,
        health.get_audio_engine_state,
    ):
        app.dependency_overrides.pop(dependency, None)


class TestHealth:
    def test_reports_the_slots_idle(self, signed_in, cap):
        answer_health()

        async def run():
            async with on(app) as api:
                return await api.get('/health')

        try:
            res = asyncio.run(run())
        finally:
            forget_health()
        assert res.json()['previews'] == {'running': 0, 'waiting': 0, 'limit': 1}
