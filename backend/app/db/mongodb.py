# backend/app/db/mongodb.py

from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()

MONGODB_USER = os.getenv("MONGODB_USER")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_URI_TPL = os.getenv("MONGODB_URI_TPL")
MONGODB_DB = os.getenv("MONGODB_DB")
MONGODB_URI = MONGODB_URI_TPL.replace("[[MONGODB_USER]]", MONGODB_USER).replace("[[MONGODB_PASSWORD]]", MONGODB_PASSWORD)
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

def get_collection(name):
    return db[name]
