"""DB layer: client reuse, parameter handling, and the seeding path.

None of these need a database. A motor client connects lazily, so it can be
constructed and inspected without a server, and every assertion here is about
what the layer builds rather than what the server returns.
"""

import asyncio

import pytest

from alfred.config import DB_NAME
from alfred.core.utils import db as dblayer

ELSEWHERE = 'mongodb://elsewhere.test:27017'


def seeds(client):
    """The hosts a client is configured for, readable before it connects.

    `client.nodes` is empty until a connection succeeds, so it cannot be used
    to assert configuration without a live server.
    """
    return list(client.topology_description.server_descriptions())


# --- client reuse ---------------------------------------------------------


def test_async_clients_are_reused_within_one_event_loop():
    """One client per loop, not one per call.

    Previously every call built a new AsyncIOMotorClient, and therefore a new
    connection pool. `alfred/core/routes/fonts.py` calls `get_db()` on every
    request, so a busy endpoint opened a pool per request.
    """

    async def check():
        return dblayer.get_client() is dblayer.get_client()

    assert asyncio.run(check())


def test_different_urls_get_different_clients():
    async def check():
        return dblayer.get_client() is not dblayer.get_client(ELSEWHERE)

    assert asyncio.run(check())


def test_a_client_is_not_shared_across_event_loops():
    """The reason the cache is keyed on the loop rather than global.

    A motor client binds to the loop that drives it; reusing one on a second
    loop raises "Event loop is closed". A module-level singleton would work in
    the server, which has one loop for its lifetime, and break anything that
    calls asyncio.run() more than once.
    """

    async def get():
        return dblayer.get_client()

    first = asyncio.run(get())
    second = asyncio.run(get())

    assert first is not second


def test_no_running_loop_yields_an_uncached_client():
    """Outside a loop, caching would bind the client to whichever loop used it
    first, so callers get a fresh one instead."""
    assert dblayer.get_client() is not dblayer.get_client()


def test_sync_clients_are_reused():
    """pymongo is loop-agnostic and thread-safe, so one client is enough."""
    assert dblayer._sync_client() is dblayer._sync_client()
    assert dblayer._sync_client() is not dblayer._sync_client(ELSEWHERE)


# --- parameters actually take effect --------------------------------------


def test_get_client_honours_db_url():
    """`get_client(db_url=...)` used to be ignored in favour of the module
    constant, so a caller could ask for one host and silently get another."""
    assert ('elsewhere.test', 27017) in seeds(dblayer.get_client(ELSEWHERE))


def test_get_db_honours_database():
    """`get_db(database=...)` used to be ignored in favour of DB_NAME."""
    assert dblayer.get_db(database='other').name == 'other'
    assert dblayer.get_db().name == DB_NAME


def test_get_db_honours_db_url():
    assert ('elsewhere.test', 27017) in seeds(dblayer.get_db(db_url=ELSEWHERE).client)


def test_get_sync_db_honours_both_parameters():
    assert dblayer.get_sync_db(database='other').name == 'other'
    assert ('elsewhere.test', 27017) in seeds(
        dblayer.get_sync_db(db_url=ELSEWHERE).client
    )


# --- the public surface ---------------------------------------------------


def test_star_import_works():
    """`__all__` held function objects rather than names, so
    `from alfred.core.utils import *` raised TypeError."""
    namespace = {}
    exec('from alfred.core.utils import *', namespace)  # noqa: S102
    for name in ('get_db', 'get_sync_db', 'get_client', 'renderer', 'sendMail'):
        assert name in namespace


def test_dead_helper_is_gone():
    """`deOid` was defined, exported, and referenced only by a commented-out
    import. Removed; this fails if it comes back without a caller."""
    assert not hasattr(dblayer, 'deOid')


# --- the seeding path -----------------------------------------------------


def test_count_documents_must_be_awaited_to_be_meaningful():
    """Pins the shape of the original defect.

    `count_documents` on a motor collection returns a Future, which is always
    truthy, so `if not db.Project.count_documents({})` never fired and the
    seeding block never ran. Kept as a test because the same mistake is easy
    to reintroduce anywhere a motor call is used in a boolean context.
    """

    async def check():
        pending = dblayer.get_db().Project.count_documents({})
        # Truthy without ever contacting the server, which is precisely why
        # the unawaited call read as "there are documents".
        truthy = bool(pending) and not (not pending)
        pending.cancel()
        return truthy

    assert asyncio.run(check())


def test_seed_startup_awaits_the_count_and_imports_absolutely():
    """The fix, asserted against the source of the startup hook.

    Reading the source is the honest check here: running the hook needs a
    live database, which would make this an integration test for a two-line
    condition.
    """
    import inspect
    from alfred import main

    source = inspect.getsource(main.seedDb)

    assert 'await db.Project.count_documents' in source
    assert 'from alfred.seed import seed' in source
    assert 'from seed import seed' not in source


def test_seed_payload_is_importable_and_shaped_like_projects():
    from alfred.seed import seed

    assert isinstance(seed, list) and seed
    for project in seed:
        assert 'logic' in project


@pytest.mark.parametrize('helper', ['get_db', 'get_client', 'get_sync_db'])
def test_helpers_do_not_connect_on_construction(helper):
    """Building a handle must not require a reachable server; every test in
    this file depends on that."""
    getattr(dblayer, helper)(
        **({'db_url': ELSEWHERE} if helper != 'get_sync_db' else {})
    )
