
# tests/test_my_challenges_routes.py
from typing import Dict, Optional, List
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId

from app.main import app
from app.core.security import get_current_user

# ---- TestClient with a fake authenticated user (dependency override) ----
@pytest.fixture(scope="module")
def client():
    fake_user = {"_id": ObjectId(), "roles": []}
    app.dependency_overrides[get_current_user] = lambda: fake_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()

def _paginated(client) -> Dict:
    resp = client.get("/my/challenges")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict) and "items" in data and isinstance(data["items"], list)
    return data

def _items(client) -> List[Dict]:
    return _paginated(client)["items"]

def _sync_and_get_one(client) -> Optional[Dict]:
    r = client.post("/my/challenges/sync")
    assert r.status_code in (200, 201)
    items = _items(client)
    return items[0] if items else None

# --- Liste + filtre par statut ---
def test_list_and_filter_status(client):
    _ = _sync_and_get_one(client)
    data = _paginated(client)
    assert "total" in data and "page" in data and "limit" in data

    r_pending = client.get("/my/challenges?status=pending")
    assert r_pending.status_code == 200
    d2 = r_pending.json()
    assert isinstance(d2, dict) and "items" in d2 and isinstance(d2["items"], list)

# --- Détail ---
def test_get_detail(client):
    uc = _sync_and_get_one(client)
    if not uc:
        pytest.skip("No UserChallenge after sync; skipping detail test.")
    r = client.get(f"/my/challenges/{uc['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == uc["id"]
    assert ("challenge" in body) or ("challenge_id" in body)

# --- Patch unitaire (notes) ---
def test_patch_updates_notes_only(client):
    uc = _sync_and_get_one(client)
    if not uc:
        pytest.skip("No UserChallenge after sync; skipping patch test.")
    r = client.patch(f"/my/challenges/{uc['id']}", json={"notes": "Première note 🤖"})
    assert r.status_code == 200
    # Relire via détail (au cas où la liste n'expose pas 'notes')
    r2 = client.get(f"/my/challenges/{uc['id']}")
    assert r2.status_code == 200
    assert r2.json().get("notes") == "Première note 🤖"

def test_patch_immutability(client):
    uc = _sync_and_get_one(client)
    if not uc:
        pytest.skip("No UserChallenge after sync; skipping immutability test.")
    # Tenter de changer un champ supposé immuable
    _ = client.patch(f"/my/challenges/{uc['id']}", json={"challenge_id": "should-not-change"})
    # Relire et vérifier qu'il n'a pas changé
    r2 = client.get(f"/my/challenges/{uc['id']}")
    assert r2.status_code == 200
    body = r2.json()
    # soit challenge embarqué, soit ref immutable
    if "challenge_id" in body:
        assert body["challenge_id"] != "should-not-change"

# --- Batch patch ---
def test_batch_patch_notes_spec_shape(client):
    _ = client.post("/my/challenges/sync")
    items = _items(client)
    if not items:
        pytest.skip("No UserChallenges to batch update.")
    targets = items[:2] if len(items) >= 2 else items[:1]

    payload = [{"uc_id": uc["id"], "notes": f"Note batch {i}"} for i, uc in enumerate(targets)]
    r = client.patch("/my/challenges", json=payload)
    assert r.status_code == 200, r.text

    resp = r.json()
    # Your API returns: {"results":[{uc_id, ok, error?}, ...], "total": N, "updated_count": K}
    assert isinstance(resp, dict)
    assert "results" in resp and isinstance(resp["results"], list)
    assert resp.get("total") == len(payload)
    assert isinstance(resp.get("updated_count"), int)

    # Vérification côté lecture: certaines APIs n'incluent pas 'notes' dans la liste -> lire le détail
    for i, uc in enumerate(targets):
        detail = client.get(f"/my/challenges/{uc['id']}")
        assert detail.status_code == 200
        assert detail.json().get("notes") == f"Note batch {i}"

# --- Robustesse entrées ---
def test_not_found_and_validation_errors(client):
    bad_id = "0"*24
    r = client.get(f"/my/challenges/{bad_id}")
    assert r.status_code in (400, 404)

    r2 = client.patch(f"/my/challenges/{bad_id}", json={"notes": "x"})
    assert r2.status_code in (400, 404)
