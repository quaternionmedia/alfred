"""M3 against a real database and a real MongoDB broker.

The pytest stack runs no render worker, which is exactly the thin stack's
situation: `GET /health` must say so, quickly, and still count the queue.
"""

import pytest

pytestmark = pytest.mark.needs_db


def test_health_with_no_worker_running(api, make_account):
    from alfred.core.routes.health import CachedRenderer, get_renderer_state
    from alfred.main import app

    # A cache of its own, so no earlier answer stands in for this one.
    fresh = CachedRenderer()
    app.dependency_overrides[get_renderer_state] = lambda: fresh
    try:
        res = api.get('/health', headers=make_account('watcher').headers)
    finally:
        app.dependency_overrides.pop(get_renderer_state, None)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['api'] == 'ok'
    assert body['db'] == 'ok'
    assert body['renderer'] == {'ok': False, 'workers': 0}
    assert isinstance(body['queue']['pending'], int)


def test_the_broker_s_queue_is_counted():
    from alfred.core.utils.tasks import pending_count

    assert pending_count() >= 0


def test_healthz_needs_nothing(api):
    assert api.get('/healthz').json() == {'ok': True}
