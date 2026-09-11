"""Tests for GET /zones and GET /zones/{code}.

Runs the real route functions against a mocked authenticated user (dependency
override) and a mocked zone service, rather than a real MongoDB - keeps this in
tests/unit/ while still exercising the actual route bodies (422/404 branches).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import zones as zones_module
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(user_id: ObjectId) -> FastAPI:
    app = FastAPI()
    app.include_router(zones_module.router)

    user = User(
        id=PyObjectId(user_id), username="regular_user", email="user@example.com", role="user"
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class TestListZones:
    @pytest.mark.asyncio
    async def test_returns_items_for_level_0(self):
        items = [{"code": "FR", "name": "France", "cache_count": 3}]
        with patch.object(
            zones_module, "get_zones_with_counts", AsyncMock(return_value=items)
        ) as mock_get:
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/zones", params={"level": 0})

        assert response.status_code == 200
        assert response.json() == {"items": items}
        mock_get.assert_awaited_once()
        assert mock_get.call_args.kwargs["level"] == 0
        assert mock_get.call_args.kwargs["country"] is None

    @pytest.mark.asyncio
    async def test_passes_country_and_type_filter_for_level_1(self):
        with patch.object(
            zones_module, "get_zones_with_counts", AsyncMock(return_value=[])
        ) as mock_get:
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/zones",
                    params={"level": 1, "country": "FR", "type": ["traditional", "mystery"]},
                )

        assert response.status_code == 200
        assert mock_get.call_args.kwargs["country"] == "FR"
        assert mock_get.call_args.kwargs["type_codes"] == ["traditional", "mystery"]

    @pytest.mark.asyncio
    async def test_missing_country_for_level_1_returns_422(self):
        with patch.object(zones_module, "get_zones_with_counts", AsyncMock()) as mock_get:
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/zones", params={"level": 1})

        assert response.status_code == 422
        assert response.json()["detail"] == "country is required for level 1 and 2."
        mock_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_country_for_level_2_returns_422(self):
        with patch.object(zones_module, "get_zones_with_counts", AsyncMock()) as mock_get:
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/zones", params={"level": 2})

        assert response.status_code == 422
        mock_get.assert_not_awaited()


class TestGetZone:
    @pytest.mark.asyncio
    async def test_returns_zone_detail(self):
        detail = {
            "code": "FR-84",
            "name": "Vaucluse",
            "cache_count": 5,
            "type_counts": [{"type_code": "traditional", "type_name": "Traditional", "count": 5}],
        }
        with patch.object(zones_module, "get_zone_detail", AsyncMock(return_value=detail)):
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/zones/FR-84")

        assert response.status_code == 200
        assert response.json() == detail

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_code(self):
        with patch.object(zones_module, "get_zone_detail", AsyncMock(return_value=None)):
            app = _make_app(ObjectId())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/zones/FR-UNKNOWN")

        assert response.status_code == 404
        assert response.json()["detail"] == "Zone 'FR-UNKNOWN' not found."
