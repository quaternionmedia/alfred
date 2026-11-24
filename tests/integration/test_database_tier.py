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


def test_the_users_email_index_starts_on_a_database_that_holds_it(db):
    """Built as fastapi-users-db-beanie 1.x left it, before the app starts.

    4.x declares it unique under the same name, which MongoDB will not build
    over it (docs/dependencies.md#the-users-email-index).
    """
    import asyncio

    from beanie import init_beanie
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.collation import Collation

    from alfred.config import DB_URL
    from alfred.core.utils.db import User

    name = f'{db.name}_email_index'
    held = db.client[name]['User']
    held.create_index(
        'email',
        name='case_insensitive_email_index',
        collation=Collation('en', strength=2),
    )
    before = User.__dict__.get('_document_settings')

    async def start():
        client = AsyncIOMotorClient(DB_URL)
        try:
            await init_beanie(database=client[name], document_models=[User])
        finally:
            client.close()

    try:
        asyncio.run(start())
        indexes = held.index_information()
    finally:
        if before is None:
            del User._document_settings
        else:
            User._document_settings = before
        db.client.drop_database(name)
    assert set(indexes) == {'_id_', 'case_insensitive_email_index'}
    assert not indexes['case_insensitive_email_index'].get('unique')


def test_an_anonymous_caller_is_refused(api):
    """The suite runs with auth on; the dev bypass must not be in play here."""
    assert api.get('/users/me').status_code == 401
