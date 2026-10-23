"""The database tier: the real app, in-process, against a real MongoDB.

Everything under `unit/` stops at the edge of the database, which is exactly
where the authorization questions start -- who may register, whose projects a
caller sees -- so none of them could be asked there. These tests drive the app
through `TestClient`, with real authentication and real queries.

Needs DB_URL. `pytest.yml` provides a MongoDB; a bare host run has none and
skips this directory (see `_has_db` in the parent conftest). Each xdist worker
has a database of its own, named in the parent conftest, and this file drops
it before and after the session.

Helpers are fixtures rather than importable functions: the test directories
are not packages, so a test module cannot import from this file reliably.
"""

import shutil
import uuid
from dataclasses import dataclass

import pytest

PASSWORD = 'correct horse battery staple'


@pytest.fixture(scope='session')
def db():
    """A synchronous handle on this worker's database, for arranging state.

    pymongo rather than the app's motor client: motor binds to an event loop,
    and the app's loop lives in TestClient's portal thread. A sync client
    belongs to no loop, so tests can insert and inspect documents directly
    without reaching into the app's.
    """
    from pymongo.errors import PyMongoError

    from alfred.core.utils.db import get_sync_db

    handle = get_sync_db()
    # Never anything else. The tier drops its database, and a misconfigured
    # run pointed at a real one must not be able to.
    assert '_test_' in handle.name, f'refusing to use {handle.name!r}'
    try:
        handle.command('ping')
    except PyMongoError as exc:
        pytest.fail(
            f'DB_URL is set but MongoDB did not answer: {exc}. A database that '
            'was promised and is missing is a failure, not a skip.'
        )
    handle.client.drop_database(handle.name)
    yield handle
    handle.client.drop_database(handle.name)


_ABSENT = object()


def _documents():
    """Every beanie Document class this process has defined."""
    from beanie import Document

    found, pending = [], [Document]
    while pending:
        for cls in pending.pop().__subclasses__():
            if cls not in found:
                found.append(cls)
                pending.append(cls)
    return found


@pytest.fixture(scope='module')
def api(db):
    """The app with its startup run, for one test module.

    One `with TestClient(...)` per module rather than per test, because beanie
    is initialised on the event loop the startup hooks run on, and motor
    clients cannot move between loops: requests made outside the context get
    a fresh loop and fail with "attached to a different loop".

    Per module rather than per session, so the initialisation can be undone
    when the module ends. `init_beanie` marks each document class initialised
    for the life of the process, and the unit tier shares that process under
    xdist: `test_config_validity` pins that a `Render` cannot be built without
    a database, and once this tier had run on a worker it could -- so those
    pins passed or failed by test order. Each class's settings are put back as
    they were found.

    `checkFonts` shells out to `fc-list`, which the API image has and a bare
    Windows or macOS host may not. It is unrelated to anything tested here,
    so it is left out where the binary is missing rather than failing every
    test in the tier on a font probe.
    """
    from fastapi.testclient import TestClient

    from alfred import main

    found = {
        cls: cls.__dict__.get('_document_settings', _ABSENT) for cls in _documents()
    }
    startup = main.app.router.on_startup
    hooks = list(startup)
    if shutil.which('fc-list') is None and main.checkFonts in startup:
        startup.remove(main.checkFonts)
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        startup[:] = hooks
        for cls in _documents():
            before = found.get(cls, _ABSENT)
            if before is not _ABSENT:
                cls._document_settings = before
            elif '_document_settings' in cls.__dict__:
                delattr(cls, '_document_settings')


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def fresh_email():
    """`fresh_email('alice')`: an address no other test will use.

    In example.com (RFC 2606), so nothing can reach a real inbox.
    """

    def make(prefix='user'):
        return f'{prefix}-{uuid.uuid4().hex[:12]}@example.com'

    return make


@pytest.fixture
def log_in(api):
    """`log_in(email)`: the bearer token the real login route issues."""

    def login(email, password=PASSWORD):
        res = api.post(
            '/auth/jwt/login', data={'username': email, 'password': password}
        )
        assert res.status_code == 200, f'login failed for {email}: {res.text}'
        return res.json()['access_token']

    return login


@pytest.fixture
def users(api, db):
    """The users collection, under whatever name beanie gave it."""
    from alfred.core.utils.db import User

    return db[User.get_motor_collection().name]


@dataclass
class Account:
    email: str
    token: str
    superuser: bool

    @property
    def headers(self):
        return {'Authorization': f'Bearer {self.token}'}


@pytest.fixture(scope='session')
def _password_hash():
    """Hashed once: bcrypt is deliberately slow, and every account shares it."""
    from fastapi_users.password import PasswordHelper

    return PasswordHelper().hash(PASSWORD)


@pytest.fixture
def make_account(api, users, fresh_email, log_in, _password_hash):
    """`make_account('alice', superuser=False)`: a user, logged in.

    Written straight to the database rather than through `/auth/register`, so
    the tier does not depend on registration being open: that is policy, and a
    server closing it must not quietly take every other test down with it.
    The login goes through the real route.
    """

    def make(prefix='user', superuser=False):
        email = fresh_email(prefix)
        users.insert_one(
            {
                'email': email,
                'hashed_password': _password_hash,
                'first_name': prefix,
                'is_active': True,
                'is_superuser': superuser,
                'is_verified': True,
            }
        )
        return Account(email=email, token=log_in(email), superuser=superuser)

    return make


@pytest.fixture
def make_project(api):
    """`make_project(account, name=None, **fields)`: create one through the API."""

    def make(account, name=None, **fields):
        body = {'name': name or f'project {uuid.uuid4().hex[:8]}', 'logic': {}}
        body.update(fields)
        res = api.post('/project', json=body, headers=account.headers)
        assert res.status_code == 200, res.text
        return res.json()

    return make


@pytest.fixture
def projects(api, db):
    """The projects collection, under whatever name beanie gave it."""
    from alfred.core.models import Project

    return db[Project.get_motor_collection().name]


@pytest.fixture
def legacy_project(projects):
    """A project stored before ownership existed: no `owner` field at all.

    Inserted directly, because no API path can create one any more -- which
    is the point.
    """
    document = {'name': f'legacy {uuid.uuid4().hex[:8]}', 'logic': {}, 'fields': []}
    inserted = projects.insert_one(document)
    return {'_id': str(inserted.inserted_id), 'name': document['name']}
