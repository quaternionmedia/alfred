"""App-level smoke tests.

These need no database: they exercise the ASGI app's routing table and the
static mount, not any handler that touches storage.
"""

from fastapi.testclient import TestClient

from alfred.main import app

client = TestClient(app)


def test_get_index():
    """Check response from / is html"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def _paths():
    return {route.path for route in app.routes if hasattr(route, 'path')}


def test_auth_routes_are_mounted_where_clients_expect_them():
    """The login route is `/auth/jwt/login`.

    This replaces a test named `test_login_fail` which POSTed to `/auth/login`
    -- a path that has never existed -- and asserted a 405. The 405 came from
    the catch-all StaticFiles mount at `/`, which serves the SPA and rejects
    anything that is not GET or HEAD. So the assertion held, the name claimed
    login was covered, and nothing about authentication was exercised. A
    typo'd route in the frontend would have passed it just as happily.
    """
    paths = _paths()

    assert '/auth/jwt/login' in paths
    assert '/auth/register' in paths
    assert '/auth/login' not in paths, 'unexpected route; update the frontend too'


def test_unmatched_post_falls_through_to_the_static_mount():
    """Pins the fall-through that made the old test look meaningful.

    Any unmatched path is handled by the SPA mount rather than returning 404,
    so a POST to a nonexistent API route answers 405, not 404. Worth pinning:
    it is the reason a test asserting 405 can pass while testing nothing, and
    it will surprise the next person who writes one.
    """
    response = client.post('/definitely-not-a-route')
    assert response.status_code == 405
