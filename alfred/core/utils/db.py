import asyncio
from functools import lru_cache
from weakref import WeakKeyDictionary

import motor.motor_asyncio
from beanie import PydanticObjectId
from fastapi_users.db import BeanieBaseUser, BeanieUserDatabase
from pydantic import Field

from alfred.config import DB_NAME, DB_URL

# Async clients are cached per event loop, not globally.
#
# A motor client binds to the loop that first drives it, and reusing one on a
# second loop raises "Event loop is closed". A plain module-level singleton or
# lru_cache would therefore work in the server -- one loop for the process
# lifetime -- and break in tests, scripts, or anything calling asyncio.run()
# more than once. Keying on the running loop gets the reuse where it matters
# without that trap. The map is weak so a finished loop's client is not held
# alive by this cache.
_clients: WeakKeyDictionary = WeakKeyDictionary()


def get_client(db_url=DB_URL):
    """Return the AsyncIOMotorClient for this event loop, creating it once.

    Called with no running loop, this returns a fresh client rather than
    caching one: a client cached outside a loop would bind to whichever loop
    happened to use it first, which is the same failure by a longer route.
    """
    client_args = dict(uuidRepresentation='standard')
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return motor.motor_asyncio.AsyncIOMotorClient(db_url, **client_args)

    per_loop = _clients.setdefault(loop, {})
    client = per_loop.get(db_url)
    if client is None:
        client = motor.motor_asyncio.AsyncIOMotorClient(db_url, **client_args)
        per_loop[db_url] = client
    return client


def get_db(db_url=DB_URL, database=DB_NAME):
    """Return an async database handle."""
    return get_client(db_url)[database]


@lru_cache(maxsize=None)
def _sync_client(db_url=DB_URL):
    """pymongo clients are loop-agnostic and thread-safe, so one is enough."""
    from pymongo import MongoClient

    return MongoClient(db_url, connect=False)


def get_sync_db(database=DB_NAME, db_url=DB_URL):
    """Return a synchronous database handle, for Celery tasks and scripts."""
    return _sync_client(db_url)[database]


class User(BeanieBaseUser[PydanticObjectId]):
    first_name: str = Field(...)


async def get_user_db():
    yield BeanieUserDatabase(User, get_db()['users'])
