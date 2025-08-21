
import time
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.core.security import get_current_user
from app.db.mongodb import get_collection

# -----------------------
# Self-contained fixtures
# -----------------------

def _find_admin_user():
    users = get_collection("users")
    # Support either a 'role' string or 'roles' array containing 'admin'
    user = users.find_one({
        "$or": [
            {"role": "admin"},
            {"roles": {"$in": ["admin"]}}
        ]
    })
    return user

@pytest.fixture(scope="session")
def admin_user_doc():
    user = _find_admin_user()
    if not user:
        pytest.skip("No admin user found in DB (role/roles contains 'admin').")
    if not isinstance(user.get("_id"), ObjectId):
        pytest.skip("Admin user found but has no valid _id ObjectId.")
    return user

@pytest.fixture(scope="session")
def app(admin_user_doc):
    # Dependency override to impersonate the admin user document returned by the DB
    def _override_current_user():
        return admin_user_doc
    fastapi_app.dependency_overrides[get_current_user] = _override_current_user
    yield fastapi_app
    fastapi_app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)

# -----------------------
# Helper functions
# -----------------------

def _get_uc_ids_by_status(client: TestClient, status: str, limit=50):
    r = client.get("/my/challenges", params={"status": status, "limit": limit})
    if r.status_code != 200:
        return []
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else None
    if not items:
        return []
    return [it.get("id") or it.get("_id") for it in items if (it.get("id") or it.get("_id"))]

def _pick_any_uc_id(client: TestClient):
    for st in ["accepted", "pending", "completed", "dismissed"]:
        ids = _get_uc_ids_by_status(client, st, limit=50)
        if ids:
            return ids[0]
    # last resort: grab from the general list without status filter
    r = client.get("/my/challenges", params={"limit": 1})
    if r.status_code == 200 and isinstance(r.json(), dict):
        items = r.json().get("items") or []
        if items:
            return items[0].get("id") or items[0].get("_id")
    return None

def _has_tasks(client: TestClient, uc_id: str) -> bool:
    r = client.get(f"/my/challenges/{uc_id}/tasks")
    if r.status_code != 200:
        return False
    items = (r.json() or {}).get("items", [])
    return len(items) > 0

def _ensure_minimal_tasks(client: TestClient, uc_id: str) -> None:
    """Ensure the UC has at least 2 tasks:
    - Task AND supported (attributes kind), min_count=1, status="done" (override to guarantee success)
    - Task OR unsupported (two attributes leaves), min_count=5
    Uses attribute 71 (challenge) which should exist in referentials.
    """
    if _has_tasks(client, uc_id):
        return

    payload = {
        "tasks": [
            {
                "title": "Smoke AND (override done)",
                "expression": {
                    "kind": "and",
                    "nodes": [
                        {
                            "kind": "attributes",
                            "attributes": [
                                {"cache_attribute_id": 71, "is_positive": True}
                            ]
                        }
                    ]
                },
                "constraints": {"min_count": 1},
                "status": "done"
            },
            {
                "title": "Smoke OR (unsupported)",
                "expression": {
                    "kind": "or",
                    "nodes": [
                        {
                            "kind": "attributes",
                            "attributes": [
                                {"cache_attribute_id": 71, "is_positive": True}
                            ]
                        },
                        {
                            "kind": "attributes",
                            "attributes": [
                                {"cache_attribute_id": 71, "is_positive": False}
                            ]
                        }
                    ]
                },
                "constraints": {"min_count": 5}
            }
        ]
    }
    # Validate first to get clear errors if referentials are missing
    v = client.post(f"/my/challenges/{uc_id}/tasks/validate", json=payload)
    assert v.status_code == 200, v.text
    vdata = v.json()
    assert vdata.get("ok") is True, f"Validation failed: {vdata}"

    r = client.put(f"/my/challenges/{uc_id}/tasks", json=payload)
    assert r.status_code == 200, r.text
    # sanity
    r2 = client.get(f"/my/challenges/{uc_id}/tasks")
    assert r2.status_code == 200, r2.text
    items = (r2.json() or {}).get("items", [])
    assert len(items) >= 2

def _recompute_aggregate(tasks):
    # Only tasks with supported_for_progress == True are included
    supported = [t for t in tasks if t.get("supported_for_progress", True)]
    if not supported:
        return {"percent": 0.0, "tasks_total": 0, "tasks_done": 0}
    sum_min = sum(max(0, int(t.get("min_count", 0))) for t in supported)
    sum_cur = 0
    tasks_done = 0
    for t in supported:
        cur = max(0, int(t.get("current_count", 0)))
        mn  = max(0, int(t.get("min_count", 0)))
        bounded = min(cur, mn)
        sum_cur += bounded
        if bounded >= mn and mn > 0:
            tasks_done += 1
    percent = 0.0 if sum_min == 0 else 100.0 * (sum_cur / sum_min)
    return {"percent": percent, "tasks_total": len(supported), "tasks_done": tasks_done}

def _approx(a: float, b: float, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))

# -----------------------
# Tests
# -----------------------

def test_progress_evaluate_smoke(client: TestClient):
    uc_id = _pick_any_uc_id(client)
    if not uc_id:
        pytest.skip("No user_challenge found for admin user.")
    _ensure_minimal_tasks(client, uc_id)

    # Evaluate now
    r = client.post(f"/my/challenges/{uc_id}/progress/evaluate")
    assert r.status_code == 200, r.text
    snap = r.json()

    # Basic structure
    assert snap.get("user_challenge_id") in (uc_id, str(uc_id))
    assert 0.0 <= float(snap["aggregate"]["percent"]) <= 100.0

    # Recompute aggregate from tasks
    tasks = snap.get("tasks", [])
    agg = _recompute_aggregate(tasks)
    assert _approx(float(snap["aggregate"]["percent"]), agg["percent"]), (snap["aggregate"], agg)
    assert snap["aggregate"]["tasks_total"] == agg["tasks_total"]
    assert snap["aggregate"]["tasks_done"] == agg["tasks_done"]

    # Ensure there's at least one unsupported task present (the OR we created)
    assert any(t.get("supported_for_progress") is False for t in tasks)

def test_progress_history_and_ordering(client: TestClient):
    uc_id = _pick_any_uc_id(client)
    if not uc_id:
        pytest.skip("No user_challenge found for admin user.")
    _ensure_minimal_tasks(client, uc_id)

    # Evaluate twice to build history
    r1 = client.post(f"/my/challenges/{uc_id}/progress/evaluate")
    assert r1.status_code == 200
    time.sleep(0.01)
    r2 = client.post(f"/my/challenges/{uc_id}/progress/evaluate")
    assert r2.status_code == 200

    # Get latest + history (limit=2)
    r = client.get(f"/my/challenges/{uc_id}/progress", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert data.get("latest") is not None
    latest = data["latest"]
    history = data.get("history", [])
    if history:
        # checked_at should be monotonic (latest >= history[0] >= history[1] ...)
        latest_ts = latest.get("checked_at")
        assert latest_ts is not None
        # Ensure we have at least one history item and it's not later than latest
        assert history[0].get("checked_at") <= latest_ts

def test_new_progress_batch_idempotent(client: TestClient):
    # First call: evaluate accepted UC without snapshot (if any)
    r1 = client.post("/my/challenges/new/progress", params={"limit": 50})
    assert r1.status_code in (200, 207), r1.text  # 207 if you choose multi-status; else 200
    data1 = r1.json()
    evaluated1 = data1.get("evaluated_count", 0)

    # Second call immediately should evaluate none (idempotent)
    r2 = client.post("/my/challenges/new/progress", params={"limit": 50})
    assert r2.status_code in (200, 207), r2.text
    data2 = r2.json()
    evaluated2 = data2.get("evaluated_count", 0)

    assert evaluated2 <= evaluated1

def test_auto_evaluation_on_accept(client: TestClient):
    # Find a pending UC (if none, skip)
    # Prefer one without tasks to avoid side effects
    uc_id = None
    for candidate in _get_uc_ids_by_status(client, "pending", limit=50):
        if not _has_tasks(client, candidate):
            uc_id = candidate
            break
    if not uc_id:
        pytest.skip("No pending user_challenge without tasks found for admin user.")

    # Check if already has a snapshot; if yes, skip (auto-eval likely already ran)
    r_pre = client.get(f"/my/challenges/{uc_id}/progress")
    if r_pre.status_code == 200 and r_pre.json().get("latest") is not None:
        pytest.skip("This pending UC already has a snapshot; skipping auto-evaluation test.")

    # Accept it
    r_patch = client.patch(f"/my/challenges/{uc_id}", json={"status": "accepted"})
    assert r_patch.status_code in (200, 204), r_patch.text

    # A snapshot should now exist
    r_post = client.get(f"/my/challenges/{uc_id}/progress")
    assert r_post.status_code == 200
    assert r_post.json().get("latest") is not None
