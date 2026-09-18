"""Tests for GET /health, GET /version, and GET /info - none of which had any
prior coverage. Covers the healthy and degraded branches of the health check.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import meta as meta_module


def _make_app():
    app = FastAPI()
    app.include_router(meta_module.router)
    return app


class TestHealth:
    @pytest.mark.asyncio
    async def test_all_checks_ok_returns_200(self):
        with (
            patch.object(meta_module, "check_mongodb", new=AsyncMock(return_value="ok")),
            patch.object(meta_module, "check_email", new=AsyncMock(return_value="ok")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"] == {"database": "ok", "email": "ok"}

    @pytest.mark.asyncio
    async def test_failing_check_returns_503_degraded(self):
        with (
            patch.object(meta_module, "check_mongodb", new=AsyncMock(return_value="error: down")),
            patch.object(meta_module, "check_email", new=AsyncMock(return_value="ok")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"


class TestVersion:
    @pytest.mark.asyncio
    async def test_returns_version_info(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/version")

        assert response.status_code == 200
        body = response.json()
        assert body["version"] == meta_module.settings.api_version
        assert body["environment"] == meta_module.settings.environment


class TestApiInfo:
    @pytest.mark.asyncio
    async def test_returns_api_info(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/info")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == meta_module.settings.app_name + " API"
        assert body["documentation"] == "/documentation"
