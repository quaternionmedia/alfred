import motor.motor_asyncio
from alfred.config import DB_URL, DB_NAME
from ..models import UserDB

def get_sync_db(database=DB_NAME):
    from pymongo import MongoClient
    sync_client = MongoClient(DB_URL, connect=False)
    return sync_client[database]

def get_client(db_url=DB_URL):
    return motor.motor_asyncio.AsyncIOMotorClient(
        DB_URL, uuidRepresentation="standard"
    )

def get_db(db_url=DB_URL, database=DB_NAME):
    return get_client(db_url=db_url)[DB_NAME]
