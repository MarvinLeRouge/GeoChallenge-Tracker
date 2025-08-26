import asyncio
from bson import ObjectId

from app.models.target_dto import TargetsPreviewPerTaskResponse
from app.services.targets_tests import preview_targets_for_uc

# Fake scope (2 tasks, both incomplete)
uc_oid = ObjectId("64a000000000000000000001")
uc_id = str(uc_oid)
task1_oid = ObjectId("64a0000000000000000000a1")
task2_oid = ObjectId("64a0000000000000000000a2")

scope_stub = [
    {"uc_id": uc_id, "task_id": str(task1_oid), "needed": 1,
     "expr": {"kind": "and", "nodes": [{"kind":"type_in", "values": []}]} },
    {"uc_id": uc_id, "task_id": str(task2_oid), "needed": 1,
     "expr": {"kind": "and", "nodes": [{"kind":"size_in", "values": []}]} },
]


def test_preview_targets_for_uc_per_task(monkeypatch):
    from app.services import targets_tests as targets_service

    # Monkeypatch async scope loader
    async def scope_async(_uc_id):
        return scope_stub
    monkeypatch.setattr(targets_service, "_load_scope_for_uc", scope_async, raising=True)

    # Monkeypatch DB get_collection for found_caches
    from app.db import mongodb as mongodb_mod
    monkeypatch.setattr(
        mongodb_mod,
        "get_collection",
        lambda name: type("C", (), {"find": lambda *a, **k: []})(),
        raising=True,
    )

    # Monkeypatch _find_caches to return 3 candidates with distance_km
    def fake_find_caches(filter_doc, limit, geo_center=None, geo_radius_km=None, bbox=None):
        return [
            {"_id": "cache-multi", "title": "Cache Multi", "loc": {"type":"Point","coordinates":[2.35,48.85]}, "distance_km": 5.0, "difficulty": 2.0, "terrain": 1.5},
            {"_id": "cache-a", "title": "Cache A", "loc": {"type":"Point","coordinates":[2.36,48.86]}, "distance_km": 8.0, "difficulty": 1.5, "terrain": 1.0},
            {"_id": "cache-b", "title": "Cache B", "loc": {"type":"Point","coordinates":[2.37,48.87]}, "distance_km": 12.0, "difficulty": 2.5, "terrain": 1.5},
        ][:limit]

    def fake_matches(cache_doc, compiled_filters):
        if cache_doc["_id"] == "cache-multi":
            return [(scope_stub[0]["uc_id"], scope_stub[0]["task_id"]), (scope_stub[1]["uc_id"], scope_stub[1]["task_id"])]
        return [(scope_stub[0]["uc_id"], scope_stub[0]["task_id"])]

    monkeypatch.setattr(targets_service, "_find_caches", fake_find_caches, raising=True)
    monkeypatch.setattr(targets_service, "_compute_matches_for_cache", fake_matches, raising=True)

    # Act
    resp = asyncio.run(
        preview_targets_for_uc(
            user_id="507f1f77bcf86cd799439011",
            uc_id=uc_id,
            mode="per_task",
            k=2,
            geo_center="48.8566,2.3522",
            geo_radius_km=50,
            bbox=None,
            max_candidates_pool=100,
        )
    )

    # Assert
    assert isinstance(resp, TargetsPreviewPerTaskResponse)
    assert resp.mode == "per_task"
    assert len(resp.buckets) == 2


def test_preview_targets_for_uc_global(monkeypatch):
    from app.services import targets_tests as targets_service

    async def scope_async(_uc_id):
        return scope_stub
    monkeypatch.setattr(targets_service, "_load_scope_for_uc", scope_async, raising=True)

    from app.db import mongodb as mongodb_mod
    monkeypatch.setattr(
        mongodb_mod,
        "get_collection",
        lambda name: type("C", (), {"find": lambda *a, **k: []})(),
        raising=True,
    )

    def fake_find_caches(filter_doc, limit, geo_center=None, geo_radius_km=None, bbox=None):
        return [
            {"_id": "cache-multi", "title": "Cache Multi", "loc": {"type":"Point","coordinates":[2.35,48.85]}, "distance_km": 3.0},
            {"_id": "cache-a", "title": "Cache A", "loc": {"type":"Point","coordinates":[2.36,48.86]}, "distance_km": 8.0},
            {"_id": "cache-b", "title": "Cache B", "loc": {"type":"Point","coordinates":[2.37,48.87]}, "distance_km": 12.0},
        ][:limit]

    def fake_matches(cache_doc, compiled_filters):
        if cache_doc["_id"] == "cache-multi":
            return [(scope_stub[0]["uc_id"], scope_stub[0]["task_id"]), (scope_stub[1]["uc_id"], scope_stub[1]["task_id"])]
        return [(scope_stub[0]["uc_id"], scope_stub[0]["task_id"])]

    monkeypatch.setattr(targets_service, "_find_caches", fake_find_caches, raising=True)
    monkeypatch.setattr(targets_service, "_compute_matches_for_cache", fake_matches, raising=True)

    resp = asyncio.run(
        preview_targets_for_uc(
            user_id="507f1f77bcf86cd799439011",
            uc_id=uc_id,
            mode="global",
            k=2,
            geo_center="48.8566,2.3522",
            geo_radius_km=50,
            bbox=None,
            max_candidates_pool=100,
        )
    )

    assert resp.mode == "global"
    assert resp.covered_pairs == 2
