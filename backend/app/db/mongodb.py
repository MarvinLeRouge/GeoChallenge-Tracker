# backend/app/api/db/mongodb.py

from pymongo import MongoClient
from app.core.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.mongodb_db]

def get_collection(name):
    return db[name]

def get_column(collection_name, column_name):
    result = [item[column_name] for item in db[collection_name].find({}, {column_name: 1, "_id": 0})]

    return result
