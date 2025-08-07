# backend/app/db/mongodb.py

from pymongo import MongoClient
from backend.app.core.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.mongodb_db]

def get_collection(name):
    return db[name]
