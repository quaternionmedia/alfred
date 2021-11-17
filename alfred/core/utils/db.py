import motor.motor_asyncio
from alfred.config import DB_URL, DB_NAME
from ..models import UserDB

def get_sync_db(database=DB_NAME):
    from pymongo import MongoClient
    sync_client = MongoClient(DB_URL, connect=False)
    return sync_client[database]

client = motor.motor_asyncio.AsyncIOMotorClient(
    DB_URL, uuidRepresentation="standard"
)
db = client[DB_NAME]
