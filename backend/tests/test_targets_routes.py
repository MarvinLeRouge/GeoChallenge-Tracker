# backend/tests/test_targets_routes.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bson import ObjectId

from app.api.routes.targets import router
from app.core import security


def make_app(fake_service_result):
    app = FastAPI()
    app.include_router(router)

    # fake user avec un vrai ObjectId valide
    oid = str(ObjectId())

    class FakeUser:
        def __init__(self, id):
            self.id = id

    def fake_auth():
        return FakeUser(oid)

    app.dependency_overrides[security.get_current_user] = fake_auth

    # monkeypatch service
    from app import services
    services.targets.preview_targets_for_uc = lambda **kwargs: fake_service_result
    return app, oid


def test_routes_preview_uc(monkeypatch):
    fake_result = {
        "mode": "per_task",
        "buckets": [],
        "meta": {"k": 5, "scope_size": 0, "uc_id": str(ObjectId())},
    }

    app, oid = make_app(fake_result)
    client = TestClient(app)

    # fabriquer un uc_id valide
    uc_id = str(ObjectId())

    # monkeypatch collection user_challenges pour matcher l'oid user + uc_id
    def fake_find_one(query, *_args, **_kwargs):
        return {"_id": ObjectId(uc_id), "user_id": ObjectId(oid)}

    monkeypatch.setattr(
        "app.api.routes.targets.get_collection",
        lambda name: type("C", (), {"find_one": fake_find_one})()
    )

    r = client.get(f"/my/challenges/{uc_id}/targets/preview")
    assert r.status_code == 200
    payload = r.json()
    assert payload["mode"] == "per_task"
    assert "buckets" in payload
