"""M3 against a real database and a real MongoDB broker.

The pytest stack runs no render worker, which is exactly the thin stack's
situation: `GET /health` must say so, quickly, and still count the queue.
"""

import threading

import pytest

pytestmark = pytest.mark.needs_db

# Long enough for the real check -- a one-second ping, then a count -- on a
# machine busy with other suites. With the route's own five seconds the check
# outlasted its timeout under that load, and the queue was answered null.
GENEROUS = 120.0


def test_health_with_no_worker_running(api, make_account):
    from alfred.core.routes.health import CachedRenderer, get_renderer_state
    from alfred.main import app

    # A cache of its own, so no earlier answer stands in for this one, and a
    # timeout of its own, so a slow broker is waited for rather than answered
    # as unknown: this is about what is reported with no worker running, and
    # the unknown answer has a test of its own below.
    fresh = CachedRenderer(timeout=GENEROUS)
    headers = make_account('watcher').headers
    app.dependency_overrides[get_renderer_state] = lambda: fresh
    try:
        res = api.get('/health', headers=headers)
    finally:
        app.dependency_overrides.pop(get_renderer_state, None)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['api'] == 'ok'
    assert body['db'] == 'ok'
    assert body['renderer'] == {'ok': False, 'workers': 0}
    assert isinstance(body['queue']['pending'], int), body


def test_a_renderer_check_that_outlasts_its_timeout_is_no_renderer_and_no_count(
    api, make_account
):
    """The answer a slow broker gets: no renderer, and a queue nobody could
    count -- `pending` null, as the contract allows -- rather than an error
    or a wait. The check is held until the answer is in, so it outlasts its
    timeout however fast or slow the machine is."""
    from alfred.core.routes.health import (
        CachedRenderer,
        RendererState,
        get_renderer_state,
    )
    from alfred.main import app

    answered = threading.Event()

    def held():
        answered.wait(GENEROUS)
        return RendererState(workers=1, pending=0)

    slow = CachedRenderer(check=held, timeout=0.05)
    headers = make_account('watcher').headers
    app.dependency_overrides[get_renderer_state] = lambda: slow
    try:
        res = api.get('/health', headers=headers)
    finally:
        answered.set()
        app.dependency_overrides.pop(get_renderer_state, None)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['db'] == 'ok'
    assert body['renderer'] == {'ok': False, 'workers': 0}
    assert body['queue'] == {'pending': None}


def test_the_broker_s_queue_is_counted():
    from alfred.core.utils.tasks import pending_count

    assert pending_count() >= 0


def test_healthz_needs_nothing(api):
    assert api.get('/healthz').json() == {'ok': True}
