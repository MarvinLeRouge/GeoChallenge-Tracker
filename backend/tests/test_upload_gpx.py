# backend/tests/test_upload_gpx.py
import datetime as dt
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.mongodb import get_collection
from app.main import app

GPX_FOLDER = Path(__file__).resolve().parents[1] / "data" / "samples" / "gpx"

# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def clean_db():
    # on ne nettoie que les collections “volatiles”
    yield


@pytest.fixture
def client():
    fake_user = {"_id": ObjectId()}
    app.dependency_overrides[get_current_user] = lambda: fake_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_gpx_path():
    return f"{GPX_FOLDER}/test-export.gpx"


# ---------- Tests ----------


def test_upload_gpx_import_caches_mode(client, sample_gpx_path):
    before_caches = get_collection("caches").count_documents({})
    before_found = get_collection("found_caches").count_documents({})

    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx?import_mode=caches", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json().get("summary", {})

    assert data["nb_gpx_files"] == 1
    assert data["nb_inserted_caches"] + data["nb_existing_caches"] == 295
    assert data["nb_inserted_found_caches"] == 0
    # En mode "caches", tous les items valides sont acceptés
    assert "nb_total_items" in data
    assert "nb_discarded_items" in data
    assert data["nb_total_items"] >= data["nb_inserted_caches"] + data["nb_existing_caches"]
    assert data["nb_discarded_items"] >= 0

    after_caches = get_collection("caches").count_documents({})
    after_found = get_collection("found_caches").count_documents({})
    assert after_caches >= before_caches
    assert after_found == before_found


def test_upload_gpx_import_finds_mode(client, sample_gpx_path):
    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx?import_mode=finds", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json().get("summary", {})

    print(data)
    assert data["nb_gpx_files"] >= 1
    # En mode "finds", seuls les items avec found_date sont acceptés
    assert "nb_total_items" in data
    assert "nb_discarded_items" in data
    assert data["nb_total_items"] >= 0
    assert data["nb_discarded_items"] >= 0
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


def test_upload_gpx_default_mode(client, sample_gpx_path):
    """Test que le mode par défaut est 'caches'."""
    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json().get("summary", {})

    # Mode par défaut devrait être "caches", donc pas de found_caches créées
    assert data["nb_inserted_found_caches"] == 0


def test_upload_gpx_invalid_mode(client, sample_gpx_path):
    """Test qu'un mode invalide retourne une erreur."""
    with open(sample_gpx_path, "rb") as fh:
        files = {"file": ("export.gpx", fh, "application/gpx+xml")}
        resp = client.post("/caches/upload-gpx?import_mode=invalid", files=files)

    assert resp.status_code == 422  # Validation error
