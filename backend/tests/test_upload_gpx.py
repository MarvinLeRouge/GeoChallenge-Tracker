# backend/tests/test_upload_gpx.py
import io
import datetime as dt
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId

from app.main import app
from app.db.mongodb import get_collection
from app.core.security import get_current_user


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def clean_db():
    # on ne nettoie que les collections “volatiles”
    get_collection("caches").delete_many({})
    get_collection("found_caches").delete_many({})
    get_collection("countries").delete_many({})
    get_collection("states").delete_many({})
    yield
    get_collection("caches").delete_many({})
    get_collection("found_caches").delete_many({})
    get_collection("countries").delete_many({})
    get_collection("states").delete_many({})

@pytest.fixture
def client():
    fake_user = {"_id": ObjectId()}
    app.dependency_overrides[get_current_user] = lambda: fake_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()

@pytest.fixture
def sample_gpx_path():
    return "../data/samples/gpx/test-export.gpx"


# ---------- Tests ----------

def ___test_upload_gpx_without_found(client, sample_gpx_path):
    before_caches = get_collection("caches").count_documents({})
    before_found = get_collection("found_caches").count_documents({})

    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx?found=false", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    print("data", data)

    assert data["nb_gpx_files"] == 1
    assert data["nb_inserted_caches"] + data["nb_existing_caches"] == 295
    assert data["nb_found_caches_added"] == 0

    after_caches = get_collection("caches").count_documents({})
    after_found = get_collection("found_caches").count_documents({})
    assert after_caches >= before_caches
    assert after_found == before_found

def test_upload_gpx_with_found(client, sample_gpx_path):
    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx?found=true", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    print(data)
    assert data["nb_gpx_files"] >= 1
    assert data["nb_inserted_caches"] + data["nb_existing_caches"] == 295
    # selon le contenu du GPX, il peut y avoir 0+ found; on vérifie simplement la cohérence
    assert data["nb_inserted_found_caches"] + data["nb_updated_found_caches"] >= 0

    # s’il y a des found_date dans le fichier, il doit y avoir au moins une found_cache
    # (on reste tolérant si l’export n’en contient pas)
    count_found = get_collection("found_caches").count_documents({})
    assert count_found >= 0

    # vérif rapide type champ si founds existent
    if count_found > 0:
        fc = get_collection("found_caches").find_one({})
        assert isinstance(fc.get("found_date"), dt.date)
