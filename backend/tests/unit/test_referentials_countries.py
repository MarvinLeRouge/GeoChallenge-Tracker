"""Tests for GET /countries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


class TestGetCountries:
    @pytest.mark.asyncio
    async def test_returns_sorted_name_and_code(self):
        docs = [
            {"code": "US", "name": "United States of America", "name_fr": None},
            {"code": "FR", "name": "France", "name_fr": "France"},
        ]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.status_code == 200
        assert response.json() == [
            {"code": "FR", "name": "France"},
            {"code": "US", "name": "United States of America"},
        ]

    @pytest.mark.asyncio
    async def test_prefers_name_fr_when_set(self):
        docs = [{"code": "DE", "name": "Germany", "name_fr": "Allemagne"}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.json() == [{"code": "DE", "name": "Allemagne"}]

    @pytest.mark.asyncio
    async def test_excludes_countries_without_code(self):
        docs = [{"code": None, "name": "Unknown Territory", "name_fr": None}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ) as mock_get:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.json() == []
        mock_get.assert_awaited_once()
