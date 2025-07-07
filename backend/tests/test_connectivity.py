# ---------------------------
# ✅ Test de communication (Python)
# ---------------------------
# Créer un script backend/tests/test_connectivity.py :

"""
import os
from pymongo import MongoClient
import requests

def test_backend_can_access_mongo():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(mongo_uri)
    dbs = client.list_database_names()
    assert isinstance(dbs, list)

def test_frontend_can_access_backend():
    res = requests.get("http://backend:8000/ping")
    assert res.status_code == 200
"""
