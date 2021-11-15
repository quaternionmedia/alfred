import motor.motor_asyncio
from fastapi_users.db import MongoDBUserDatabase
from config import DB_URL
from models import UserDB

def get_sync_db(database='alfred'):
    from pymongo import MongoClient
    sync_client = MongoClient(DB_URL, connect=False)
    return sync_client[database]

client = motor.motor_asyncio.AsyncIOMotorClient(
    DB_URL, uuidRepresentation="standard"
)
db = client.alfred
usersCollection = db["users"]


async def get_user_db():
    yield MongoDBUserDatabase(UserDB, usersCollection)
