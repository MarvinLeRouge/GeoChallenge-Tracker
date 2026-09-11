# backend/tests/unit/test_admin_geo_routes.py
"""Tests for /admin/geo routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import admin_geo as admin_geo_module
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(role: str) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_geo_module.router)
    user = User(id=PyObjectId(ObjectId()), username="u", email="u@example.com", role=role)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class TestListMissingCountries:
    @pytest.mark.asyncio
    async def test_returns_items_for_admin(self):
        items = [{"code": "DE", "found_count": 5}]
        with patch.object(admin_geo_module, "get_missing_countries", AsyncMock(return_value=items)):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/admin/geo/missing-countries")

        assert response.status_code == 200
        assert response.json() == {"items": items}

    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self):
        with patch.object(admin_geo_module, "get_missing_countries", AsyncMock()) as mock_get:
            app = _make_app("user")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/admin/geo/missing-countries")

        assert response.status_code == 403
        mock_get.assert_not_awaited()


class TestUploadGeoFile:
    @pytest.mark.asyncio
    async def test_uploads_for_admin(self):
        result = {
            "country_code": "FR",
            "level": 1,
            "features_count": 1,
            "inserted": 1,
            "updated": 0,
        }
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock(return_value=result)):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={
                        "file": (
                            "adm1.geojson",
                            b'{"type":"FeatureCollection","features":[]}',
                            "application/json",
                        )
                    },
                )

        assert response.status_code == 200
        assert response.json() == result

    @pytest.mark.asyncio
    async def test_rejects_invalid_country_code(self):
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock()) as mock_upload:
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/fra/upload",
                    params={"level": 1},
                    files={"file": ("x.geojson", b"{}", "application/json")},
                )

        assert response.status_code == 422
        mock_upload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_422_on_contract_violation(self):
        with patch.object(
            admin_geo_module, "upload_zone_level", AsyncMock(side_effect=ValueError("bad contract"))
        ):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={
                        "file": (
                            "x.geojson",
                            b'{"type":"FeatureCollection","features":[]}',
                            "application/json",
                        )
                    },
                )

        assert response.status_code == 422
        assert response.json()["detail"] == "bad contract"

    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self):
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock()) as mock_upload:
            app = _make_app("user")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={"file": ("x.geojson", b"{}", "application/json")},
                )

        assert response.status_code == 403
        mock_upload.assert_not_awaited()
