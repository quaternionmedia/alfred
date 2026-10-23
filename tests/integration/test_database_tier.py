"""The database tier itself: what the other tests in this directory stand on.

If these fail, nothing else here is evidence of anything -- an authorization
test that cannot log in, or that shares a database with another worker,
passes and fails for reasons unrelated to what it names.
"""

import pytest

pytestmark = pytest.mark.needs_db


def test_each_worker_has_a_database_of_its_own(db):
    """Settled in the parent conftest, before the app was imported.

    Shared, one worker's projects would appear in another's "you only see
    your own" assertions.
    """
    from os import environ

    from alfred.config import DB_NAME

    assert db.name == DB_NAME
    assert db.name.endswith(environ.get('PYTEST_XDIST_WORKER', 'main'))


def test_a_real_login_reaches_a_real_user(api, make_account):
    """End to end through fastapi-users: password hash, JWT, user lookup."""
    account = make_account('tier')

    res = api.get('/users/me', headers=account.headers)

    assert res.status_code == 200, res.text
    assert res.json()['email'] == account.email


def test_an_anonymous_caller_is_refused(api):
    """The suite runs with auth on; the dev bypass must not be in play here."""
    assert api.get('/users/me').status_code == 401
