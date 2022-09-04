import motor.motor_asyncio
from alfred.config import DB_URL, DB_NAME
from typing import List
from pydantic import Field
from fastapi_users.db import BeanieBaseUser, BeanieUserDatabase
from beanie import PydanticObjectId


def get_sync_db(database=DB_NAME):
    from pymongo import MongoClient

    sync_client = MongoClient(DB_URL, connect=False)
    return sync_client[database]


def get_client(db_url=DB_URL, database=DB_NAME):
    return motor.motor_asyncio.AsyncIOMotorClient(DB_URL, uuidRepresentation="standard")


def get_db(db_url=DB_URL, database=DB_NAME):
    return get_client(db_url=db_url)[DB_NAME]


class User(BeanieBaseUser[PydanticObjectId]):
    first_name: str = Field(...)


async def get_user_db():
    yield BeanieUserDatabase(User, get_db()['users'])


def deOid(results: List):
    """De-ObjectID
    Takes a list of objects, and converts the objectID (_id) to a string for serialization"""
    for r in results:
        r['_id'] = str(r['_id'])
    return results
