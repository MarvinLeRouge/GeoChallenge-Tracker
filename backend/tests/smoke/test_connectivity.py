# ---------------------------
# ✅ Test de communication (Python)
# ---------------------------
# Créer un script backend/tests/test_connectivity.py :

from dotenv import load_dotenv
from rich import print

from app.db.mongodb import client as mg_client

load_dotenv()


def test_backend_can_access_mongo():
    dbs = mg_client.list_database_names()
    print(f"🔎 Bases Mongo accessibles : {dbs}")
    assert isinstance(dbs, list)


"""
def test_frontend_can_access_backend():
    res = requests.get("http://backend:8000/ping")
    assert res.status_code == 200
"""

if __name__ == "__main__":
    test_backend_can_access_mongo()
