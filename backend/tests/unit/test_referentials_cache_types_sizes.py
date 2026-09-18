"""Tests for GET /cache_types and GET /cache_sizes - neither had any prior
coverage (only GET /countries was tested).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import referentials as referentials_module


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(referentials_module.router)
    return app


def _mock_collection(docs: list[dict]) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.find.return_value = cursor
    return coll


class TestGetCacheTypes:
    @pytest.mark.asyncio
    async def test_returns_types_with_string_ids(self):
        doc_id = ObjectId()
        docs = [{"_id": doc_id, "code": "traditional", "label": "Traditional Cache"}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/cache_types")

        assert response.status_code == 200
        body = response.json()
        assert body[0]["_id"] == str(doc_id)
        assert body[0]["code"] == "traditional"


class TestGetCacheSizes:
    @pytest.mark.asyncio
    async def test_returns_sizes_with_string_ids(self):
        doc_id = ObjectId()
        docs = [{"_id": doc_id, "code": "regular", "label": "Regular"}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/cache_sizes")

        assert response.status_code == 200
        body = response.json()
        assert body[0]["_id"] == str(doc_id)
        assert body[0]["code"] == "regular"
