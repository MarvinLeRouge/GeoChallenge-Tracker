"""
Integration tests for the /zones endpoints.

Tests:
- GET /zones requires authentication
- GET /zones returns zones for a given country/level (per-user found caches)
- GET /zones/{code} returns zone detail (per-user found caches)
- GET /zones/{code} returns 404 for unknown code
"""

from __future__ import annotations

from datetime import datetime

import pytest
from bson import ObjectId

# The test user ObjectId matches the one used by the admin_token fixture in conftest.py
TEST_USER_ID = ObjectId("507f1f77bcf86cd799439011")


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
async def zones_fixtures(test_db):
    """Seeds administrative_zones, caches, and found_caches for zone endpoint tests.

    The authenticated test user (TEST_USER_ID) has found both test caches so that
    all count assertions reflect per-user logic.
    """
    await test_db.administrative_zones.delete_many({"code": {"$in": ["FR-TEST-1", "FR-TEST-2"]}})
    await test_db.administrative_zones.insert_many(
        [
            {
                "code": "FR-TEST-1",
                "country_code": "FR",
                "level": 1,
                "name": "Test Région",
                "parent_code": None,
                "geojson_file": "FR/regions.geojson",
                "feature_code": "TEST1",
                "bbox": [0.0, 0.0, 5.0, 5.0],
            },
            {
                "code": "FR-TEST-2",
                "country_code": "FR",
                "level": 2,
                "name": "Test Département",
                "parent_code": "FR-TEST-1",
                "geojson_file": "FR/departements.geojson",
                "feature_code": "TEST2",
                "bbox": [0.0, 0.0, 2.0, 2.0],
            },
        ]
    )

    await test_db.cache_types.update_one(
        {"code": "traditional"},
        {"$setOnInsert": {"code": "traditional", "name": "Traditionnel"}},
        upsert=True,
    )
    ct_doc = await test_db.cache_types.find_one({"code": "traditional"})
    ct_id = ct_doc["_id"]

    await test_db.caches.delete_many({"GC": {"$in": ["GCTEST01", "GCTEST02"]}})
    result = await test_db.caches.insert_many(
        [
            {
                "GC": "GCTEST01",
                "title": "Cache de test 1",
                "lat": 1.0,
                "lon": 1.0,
                "difficulty": 2.0,
                "terrain": 2.0,
                "type_id": ct_id,
                "zones": {"country": "FR", "level1": "FR-TEST-1", "level2": "FR-TEST-2"},
            },
            {
                "GC": "GCTEST02",
                "title": "Cache de test 2",
                "lat": 1.5,
                "lon": 1.5,
                "difficulty": 3.0,
                "terrain": 3.0,
                "type_id": ct_id,
                "zones": {"country": "FR", "level1": "FR-TEST-1", "level2": "FR-TEST-2"},
            },
        ]
    )
    cache_ids = result.inserted_ids

    # Seed found_caches: the test user has found both caches
    await test_db.found_caches.delete_many(
        {"user_id": TEST_USER_ID, "cache_id": {"$in": cache_ids}}
    )
    await test_db.found_caches.insert_many(
        [
            {
                "user_id": TEST_USER_ID,
                "cache_id": cache_ids[0],
                "found_date": datetime(2024, 1, 1),
                "created_at": datetime(2024, 1, 1),
                "updated_at": datetime(2024, 1, 1),
            },
            {
                "user_id": TEST_USER_ID,
                "cache_id": cache_ids[1],
                "found_date": datetime(2024, 1, 2),
                "created_at": datetime(2024, 1, 2),
                "updated_at": datetime(2024, 1, 2),
            },
        ]
    )

    yield test_db

    await test_db.administrative_zones.delete_many({"code": {"$in": ["FR-TEST-1", "FR-TEST-2"]}})
    await test_db.caches.delete_many({"GC": {"$in": ["GCTEST01", "GCTEST02"]}})
    await test_db.found_caches.delete_many(
        {"user_id": TEST_USER_ID, "cache_id": {"$in": cache_ids}}
    )


# ── Tests: authentication ──────────────────────────────────────────────────────


class TestZonesAuth:
    """Tests that /zones endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_zones_requires_auth(self, client):
        response = await client.get("/zones", params={"country": "FR", "level": 1})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_zone_requires_auth(self, client):
        response = await client.get("/zones/FR-TEST-1")
        assert response.status_code == 401


# ── Tests: GET /zones ──────────────────────────────────────────────────────────


class TestListZones:
    """Tests for GET /zones."""

    @pytest.mark.asyncio
    async def test_list_zones_returns_items(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones", params={"country": "FR", "level": 1})
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        codes = [item["code"] for item in data["items"]]
        assert "FR-TEST-1" in codes

    @pytest.mark.asyncio
    async def test_list_zones_level2(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones", params={"country": "FR", "level": 2})
        assert response.status_code == 200
        data = response.json()
        codes = [item["code"] for item in data["items"]]
        assert "FR-TEST-2" in codes

    @pytest.mark.asyncio
    async def test_list_zones_cache_count(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones", params={"country": "FR", "level": 1})
        assert response.status_code == 200
        items = response.json()["items"]
        test_item = next((i for i in items if i["code"] == "FR-TEST-1"), None)
        assert test_item is not None
        assert test_item["cache_count"] == 2

    @pytest.mark.asyncio
    async def test_list_zones_type_filter_match(self, auth_client, zones_fixtures):
        response = await auth_client.get(
            "/zones", params={"country": "FR", "level": 1, "type": "traditional"}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        codes = [i["code"] for i in items]
        assert "FR-TEST-1" in codes

    @pytest.mark.asyncio
    async def test_list_zones_type_filter_no_match(self, auth_client, zones_fixtures):
        response = await auth_client.get(
            "/zones", params={"country": "FR", "level": 1, "type": "mystery"}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        codes = [i["code"] for i in items]
        assert "FR-TEST-1" not in codes

    @pytest.mark.asyncio
    async def test_list_zones_missing_country_returns_422(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones", params={"level": 1})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_zones_invalid_level_returns_422(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones", params={"country": "FR", "level": 5})
        assert response.status_code == 422


# ── Tests: GET /zones/{code} ───────────────────────────────────────────────────


class TestGetZoneDetail:
    """Tests for GET /zones/{code}."""

    @pytest.mark.asyncio
    async def test_get_zone_detail_returns_data(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones/FR-TEST-2")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "FR-TEST-2"
        assert data["name"] == "Test Département"
        assert data["cache_count"] == 2
        assert len(data["caches"]) == 2

    @pytest.mark.asyncio
    async def test_get_zone_detail_cache_fields(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones/FR-TEST-2")
        assert response.status_code == 200
        cache = response.json()["caches"][0]
        assert "GC" in cache
        assert "title" in cache
        assert "difficulty" in cache
        assert "terrain" in cache

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones/FR-NONEXISTENT-9999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_zone_type_filter(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones/FR-TEST-2", params={"type": "traditional"})
        assert response.status_code == 200
        data = response.json()
        assert data["cache_count"] == 2

    @pytest.mark.asyncio
    async def test_get_zone_type_filter_no_match(self, auth_client, zones_fixtures):
        response = await auth_client.get("/zones/FR-TEST-2", params={"type": "mystery"})
        assert response.status_code == 200
        data = response.json()
        assert data["cache_count"] == 0
        assert data["caches"] == []
