"""Tests for GET /caches/within-bbox and GET /caches/within-radius, previously
untested. Covers the compact/non-compact branches, optional type_id/size_id
filters (via _oid), and the try/except -> 400 guard on within-radius when the
2dsphere index is missing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import caches as caches_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(caches_module.router)

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


async def _agen(docs):
    for doc in docs:
        yield doc


class TestWithinBbox:
    @pytest.mark.asyncio
    async def test_non_compact_with_type_and_size_filters(self):
        doc = {"_id": ObjectId(), "GC": "GC1", "title": "Cache 1"}
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.skip = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=_agen([doc]))

        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)
        coll.count_documents = AsyncMock(return_value=1)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-bbox",
                    params={
                        "min_lat": 45.0,
                        "min_lon": 5.0,
                        "max_lat": 46.0,
                        "max_lon": 6.0,
                        "type_id": str(ObjectId()),
                        "size_id": str(ObjectId()),
                        "compact": "false",
                    },
                )

        assert response.status_code == 200
        assert response.json()["items"][0]["GC"] == "GC1"

    @pytest.mark.asyncio
    async def test_invalid_type_id_returns_400(self):
        coll = AsyncMock()
        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-bbox",
                    params={
                        "min_lat": 45.0,
                        "min_lon": 5.0,
                        "max_lat": 46.0,
                        "max_lon": 6.0,
                        "type_id": "not-an-object-id",
                    },
                )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_compact_default_uses_aggregate(self):
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agen([]))
        coll.count_documents = AsyncMock(return_value=0)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-bbox",
                    params={"min_lat": 45.0, "min_lon": 5.0, "max_lat": 46.0, "max_lon": 6.0},
                )

        assert response.status_code == 200
        coll.aggregate.assert_called_once()


class TestWithinRadius:
    @pytest.mark.asyncio
    async def test_happy_path_compact_and_count(self):
        doc = {"_id": ObjectId(), "GC": "GC1", "title": "Cache 1", "dist_meters": 100.0}
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agen([doc]))
        coll.count_documents = AsyncMock(return_value=1)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-radius",
                    params={
                        "lat": 45.0,
                        "lon": 5.0,
                        "radius_km": 5,
                        "type_id": str(ObjectId()),
                        "size_id": str(ObjectId()),
                    },
                )

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["GC"] == "GC1"
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_failure_returns_400_missing_index(self):
        coll = AsyncMock()

        def _raise(*args, **kwargs):
            raise RuntimeError("no 2dsphere index")

        coll.aggregate = MagicMock(side_effect=_raise)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-radius",
                    params={"lat": 45.0, "lon": 5.0},
                )

        assert response.status_code == 400
        assert "2dsphere" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_size_id_returns_400(self):
        coll = AsyncMock()
        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/caches/within-radius",
                    params={"lat": 45.0, "lon": 5.0, "size_id": "not-an-object-id"},
                )

        assert response.status_code == 400
