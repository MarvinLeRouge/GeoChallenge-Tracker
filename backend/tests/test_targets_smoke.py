# tests/test_targets_api_smoke.py
import os

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.db.mongodb import get_collection
from app.main import app

# -----------------------
# Helpers
# -----------------------


def _login_and_headers(client: TestClient):
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    assert username and password, "ADMIN_USERNAME / ADMIN_PASSWORD non définis"

    # OAuth2PasswordRequestForm -> x-www-form-urlencoded
    r = client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    js = r.json()
    token = js.get("access_token")
    assert token, f"no access_token in response: {js}"
    return {"Authorization": f"Bearer {token}"}, username


def _admin_user_id(admin_username: str):
    u = get_collection("users").find_one({"username": admin_username}, {"_id": 1})
    assert u, f"user '{admin_username}' introuvable en DB"
    return u["_id"]


def _one_multitask_uc_for_user(user_id: ObjectId):
    # UC avec au moins 2 tasks pour CE user
    agg = list(
        get_collection("user_challenge_tasks").aggregate(
            [
                {
                    "$lookup": {
                        "from": "user_challenges",
                        "localField": "user_challenge_id",
                        "foreignField": "_id",
                        "as": "uc",
                    }
                },
                {"$unwind": "$uc"},
                {"$match": {"uc.user_id": user_id}},
                {"$group": {"_id": "$user_challenge_id", "cnt": {"$sum": 1}}},
                {"$match": {"cnt": {"$gte": 2}}},
                {"$limit": 1},
            ]
        )
    )
    assert agg, "Aucun user_challenge multi-tasks pour cet utilisateur"
    uc_id = agg[0]["_id"]
    uc = get_collection("user_challenges").find_one({"_id": uc_id})
    assert uc, "user_challenge introuvable"
    return uc


# -----------------------
# Fixtures
# -----------------------


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_context(client):
    headers, admin_username = _login_and_headers(client)
    admin_uid = _admin_user_id(admin_username)
    return client, headers, admin_uid


@pytest.fixture()
def cleanup_targets():
    created_for_uc = []
    yield created_for_uc
    # nettoyage NON destructif (ne supprime que ce que le test a marqué)
    if created_for_uc:
        get_collection("targets").delete_many({"user_challenge_id": {"$in": created_for_uc}})


# -----------------------
# Tests
# -----------------------


def test_targets_e2e_api(auth_context, cleanup_targets):
    client, headers, user_id = auth_context
    uc = _one_multitask_uc_for_user(user_id)
    uc_id = str(uc["_id"])

    # 1) Evaluate (force)
    r = client.post(
        f"/my/challenges/{uc_id}/targets/evaluate",
        params={"force": True, "limit_per_task": 100, "hard_limit_total": 1000},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    js = r.json()
    assert js["ok"] is True
    # mémorise l'UC pour cleanup
    cleanup_targets.append(ObjectId(uc_id))

    # 2) List UC
    r = client.get(
        f"/my/challenges/{uc_id}/targets",
        params={"page": 1, "limit": 20},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert "items" in out and isinstance(out["items"], list)
    items = out["items"]

    # Cohérences de base
    found_ids = set(
        x["cache_id"]
        for x in get_collection("found_caches").find(
            {"user_id": user_id}, {"cache_id": 1, "_id": 0}
        )
    )
    username = (get_collection("users").find_one({"_id": user_id}, {"username": 1}) or {}).get(
        "username"
    )
    task_ids = set(
        t["_id"]
        for t in get_collection("user_challenge_tasks").find(
            {"user_challenge_id": ObjectId(uc_id)}, {"_id": 1}
        )
    )

    for it in items:
        assert it["user_challenge_id"] == uc_id
        assert it["cache_id"]
        assert isinstance(it["score"], float) and it["score"] >= 0.0
        # matched_task_ids ⊆ tasks du UC
        assert set(map(ObjectId, it["matched_task_ids"])).issubset(task_ids)
        # pas déjà trouvée
        assert ObjectId(it["cache_id"]) not in found_ids
        # owner != username
        cache = get_collection("caches").find_one({"_id": ObjectId(it["cache_id"])}, {"owner": 1})
        if username and cache and "owner" in cache:
            assert cache["owner"] != username


def test_targets_skip_and_force_api(auth_context, cleanup_targets):
    client, headers, user_id = auth_context
    uc = _one_multitask_uc_for_user(user_id)
    uc_id = str(uc["_id"])
    cleanup_targets.append(ObjectId(uc_id))

    # 1) evaluate force
    r1 = client.post(
        f"/my/challenges/{uc_id}/targets/evaluate",
        params={"force": True, "limit_per_task": 50, "hard_limit_total": 500},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    total_1 = r1.json()["total"]

    # 2) evaluate avec caps minuscules => skip attendu
    r2 = client.post(
        f"/my/challenges/{uc_id}/targets/evaluate",
        params={"limit_per_task": 1, "hard_limit_total": 1},  # cap = min(1, 5) = 1
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json()
    assert js2.get("skipped") is True
    assert js2["total"] >= total_1

    # 3) evaluate avec force => recalc
    r3 = client.post(
        f"/my/challenges/{uc_id}/targets/evaluate",
        params={"force": True},
        headers=headers,
    )
    assert r3.status_code == 200, r3.text
    assert r3.json().get("ok") is True


def test_targets_nearby_api(auth_context, cleanup_targets):
    client, headers, user_id = auth_context
    uc = _one_multitask_uc_for_user(user_id)
    uc_id = str(uc["_id"])
    cleanup_targets.append(ObjectId(uc_id))

    # s'assurer qu'on a des targets
    client.post(
        f"/my/challenges/{uc_id}/targets/evaluate",
        params={"force": True, "limit_per_task": 50, "hard_limit_total": 500},
        headers=headers,
    )

    # nearby avec fallback sur la position user si non fournie
    r = client.get(
        f"/my/challenges/{uc_id}/targets/nearby",
        params={"radius_km": 30, "page": 1, "limit": 10},
        headers=headers,
    )
    # si l'utilisateur n'a pas de position, l’API renvoie 422 — on l’accepte (test non destructif)
    if r.status_code == 422:
        return
    assert r.status_code == 200, r.text
    js = r.json()
    assert "items" in js
    for it in js["items"]:
        assert "distance_km" in it
