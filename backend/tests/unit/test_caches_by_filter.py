"""Tests for POST /caches/by-filter, previously untested. Covers the compact
(aggregate, direct async-iteration) branch, the non-compact (find/sort/skip/
limit) branch, and pagination math.
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


class TestByFilterCompact:
    @pytest.mark.asyncio
    async def test_compact_search_returns_aggregated_items_with_pagination(self):
        doc = {"_id": ObjectId(), "GC": "GC1", "title": "Cache 1"}
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agen([doc]))
        coll.count_documents = AsyncMock(return_value=1)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/by-filter",
                    json={
                        "q": "treasure",
                        "difficulty": {"min": 1, "max": 3},
                        "terrain": {"min": 1, "max": 3},
                        "placed_after": "2020-01-01T00:00:00",
                        "attr_pos": [str(ObjectId())],
                        "attr_neg": [str(ObjectId())],
                        "bbox": {
                            "min_lat": 45.0,
                            "min_lon": 5.0,
                            "max_lat": 46.0,
                            "max_lon": 6.0,
                        },
                        "page": 1,
                        "page_size": 20,
                    },
                )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["nb_pages"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["GC"] == "GC1"


class TestByFilterNonCompact:
    @pytest.mark.asyncio
    async def test_non_compact_search_uses_find_sort_skip_limit(self):
        doc = {"_id": ObjectId(), "GC": "GC2", "title": "Cache 2"}
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
                response = await client.post(
                    "/caches/by-filter",
                    params={"compact": "false"},
                    json={"sort": "difficulty", "page": 1, "page_size": 10},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["GC"] == "GC2"
        coll.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_size_is_clamped_to_200(self):
        coll = AsyncMock()
        coll.aggregate = MagicMock(return_value=_agen([]))
        coll.count_documents = AsyncMock(return_value=0)

        with patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/by-filter",
                    json={"page_size": 9999},
                )

        assert response.status_code == 200
        assert response.json()["page_size"] == 200
