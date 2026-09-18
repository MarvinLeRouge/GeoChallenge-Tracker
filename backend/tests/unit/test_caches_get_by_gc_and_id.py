"""Tests for GET /caches/{gc} and GET /caches/by-id/{id}, previously
untested. Both use an aggregate(...).to_list(length=None) cursor and share
the same not-found (404) shape; by-id additionally validates the ObjectId
(400 on invalid input).
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


def _agg_returning(docs):
    return MagicMock(to_list=AsyncMock(return_value=docs))


class TestGetByGc:
    @pytest.mark.asyncio
    async def test_existing_cache_is_returned(self):
        doc = {"_id": ObjectId(), "GC": "GC123", "title": "Sample"}
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agg_returning([doc]))

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/caches/GC123")

        assert response.status_code == 200
        assert response.json()["GC"] == "GC123"

    @pytest.mark.asyncio
    async def test_unknown_gc_returns_404(self):
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agg_returning([]))

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/caches/GCUNKNOWN")

        assert response.status_code == 404
        assert response.json()["detail"] == "Cache not found"


class TestGetById:
    @pytest.mark.asyncio
    async def test_existing_cache_is_returned(self):
        cache_id = ObjectId()
        doc = {"_id": cache_id, "GC": "GC456", "title": "Sample"}
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agg_returning([doc]))

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/caches/by-id/{cache_id}")

        assert response.status_code == 200
        assert response.json()["GC"] == "GC456"

    @pytest.mark.asyncio
    async def test_unknown_id_returns_404(self):
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agg_returning([]))

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/caches/by-id/{ObjectId()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Cache not found"

    @pytest.mark.asyncio
    async def test_invalid_object_id_returns_400(self):
        coll = AsyncMock()
        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/caches/by-id/not-an-object-id")

        assert response.status_code == 400
