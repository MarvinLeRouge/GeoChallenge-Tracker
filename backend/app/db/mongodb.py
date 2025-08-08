# backend/app/api/db/mongodb.py

from pymongo import MongoClient
from app.core.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.mongodb_db]

def get_collection(name):
    return db[name]
