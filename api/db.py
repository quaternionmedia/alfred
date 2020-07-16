from pymongo import MongoClient
from config import DB_URL

client = MongoClient(DB_URL, connect=False)
db = client.alfred
