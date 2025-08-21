import asyncio
from bson import ObjectId

from app.models.target_dto import TargetsPreviewGlobalResponse
from app.services.targets import preview_targets_multi_uc

# Fake scope for multi-UC (two UCs, one task each, both incomplete)
uc1 = str(ObjectId("64a000000000000000000101"))
uc2 = str(ObjectId("64a000000000000000000202"))
t1  = str(ObjectId("64a0000000000000000001a1"))
t2  = str(ObjectId("64a0000000000000000002a2"))

scope_stub_multi = [
    {"uc_id": uc1, "task_id": t1, "needed": 1,
     "expr": {"kind": "and", "nodes": [{"kind":"type_in", "values": []}]} },
    {"uc_id": uc2, "task_id": t2, "needed": 1,
     "expr": {"kind": "and", "nodes": [{"kind":"size_in", "values": []}]} },
]


def test_preview_targets_multi_global(monkeypatch):
    from app.services import targets as targets_service

    # Monkeypatch async scope loader (multi-UC)
    async def scope_async(_user_id):
        return scope_stub_multi
    monkeypatch.setattr(targets_service, "_load_scope_multi_uc", scope_async, raising=True)

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
            {"_id": "cache-multi", "title": "Cache Multi", "loc": {"type":"Point","coordinates":[2.35,48.85]}, "distance_km": 4.0},
            {"_id": "cache-a", "title": "Cache A", "loc": {"type":"Point","coordinates":[2.36,48.86]}, "distance_km": 7.0},
            {"_id": "cache-b", "title": "Cache B", "loc": {"type":"Point","coordinates":[2.37,48.87]}, "distance_km": 9.0},
        ][:limit]

    def fake_matches(cache_doc, compiled_filters):
        # 'cache-multi' matches both tasks across UCs; others match only the first one
        if cache_doc["_id"] == "cache-multi":
            return [(scope_stub_multi[0]["uc_id"], scope_stub_multi[0]["task_id"]),
                    (scope_stub_multi[1]["uc_id"], scope_stub_multi[1]["task_id"])]
        return [(scope_stub_multi[0]["uc_id"], scope_stub_multi[0]["task_id"])]

    monkeypatch.setattr(targets_service, "_find_caches", fake_find_caches, raising=True)
    monkeypatch.setattr(targets_service, "_compute_matches_for_cache", fake_matches, raising=True)

    # Act
    resp = asyncio.run(
        preview_targets_multi_uc(
            user_id="507f1f77bcf86cd799439011",
            mode="global",
            k=2,
            geo_center="48.8566,2.3522",
            geo_radius_km=50,
            bbox=None,
            max_candidates_pool=100,
        )
    )

    # Assert
    assert isinstance(resp, TargetsPreviewGlobalResponse)
    assert resp.mode == "global"
    assert resp.covered_pairs == 2
    assert len(resp.selection) >= 1
    # the first selection should include a multi-cover target (2 matched pairs) in this setup
    if resp.selection:
        assert len(resp.selection[0].matched) >= 1
