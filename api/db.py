from pymongo import MongoClient

client = MongoClient('mongodb://db:27017', connect=False)
db = client.alfred
