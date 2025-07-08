# ---------------------------
# ✅ Test de communication (Python)
# ---------------------------
# Créer un script backend/tests/test_connectivity.py :

import os
from pymongo import MongoClient
import requests
from rich import print
from dotenv import load_dotenv
load_dotenv()

def test_backend_can_access_mongo():
    MONGODB_USER = os.getenv("MONGODB_USER")
    MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
    MONGODB_URI_TPL = os.getenv("MONGODB_URI_TPL")
    MONGODB_DB = os.getenv("MONGODB_DB")
    MONGODB_URI = MONGODB_URI_TPL.replace("[[MONGODB_USER]]", MONGODB_USER).replace("[[MONGODB_PASSWORD]]", MONGODB_PASSWORD)
    client = MongoClient(MONGODB_URI)
    dbs = client.list_database_names()
    print(f"🔎 Bases Mongo accessibles : {dbs}")
    assert isinstance(dbs, list)

"""
def test_frontend_can_access_backend():
    res = requests.get("http://backend:8000/ping")
    assert res.status_code == 200
"""