"""Tests that the admin upload routes in maintenance.py enforce the shared
upload size cap (read_upload_file_with_limit), closing the Codecov patch-coverage
gap left by PR #78 (fix/upload-routes-missing-size-cap).

Runs the real route functions (POST /maintenance/upload-gpx and
POST /maintenance/users/{user_id}/found-caches/sync) against a mocked admin
user (dependency override) and mocked service layer, rather than a real
MongoDB - keeps this in tests/unit/ while still exercising the actual route
body, including the `get_settings()` + `read_upload_file_with_limit()` lines.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(
        id=ObjectId(),
        username="admin",
        email="admin@example.com",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


def _small_settings():
    settings = MagicMock()
    settings.max_upload_bytes = 100
    return settings


class TestUploadGpxSizeLimit:
    @pytest.mark.asyncio
    async def test_oversized_file_rejected_before_import(self):
        app = _make_app()

        with (
            patch.object(maintenance_module, "get_settings", return_value=_small_settings()),
            patch.object(maintenance_module, "import_gpx_payload") as mock_import,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/upload-gpx",
                    files={"file": ("caches.gpx", b"x" * 500, "application/gpx+xml")},
                )

        assert response.status_code == 413
        mock_import.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_within_limit_is_imported(self):
        app = _make_app()

        with (
            patch.object(maintenance_module, "get_settings", return_value=_small_settings()),
            patch.object(
                maintenance_module,
                "import_gpx_payload",
                new=AsyncMock(return_value={"imported": 1}),
            ) as mock_import,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/upload-gpx",
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 200
        assert response.json()["summary"] == {"imported": 1}
        mock_import.assert_awaited_once()
        assert mock_import.call_args.kwargs["payload"] == b"<gpx></gpx>"
        assert mock_import.call_args.kwargs["force_update_attributes"] is True


class TestMaintenanceSyncFoundCachesSizeLimit:
    @pytest.mark.asyncio
    async def test_oversized_file_rejected_before_sync(self):
        app = _make_app()
        target_user_id = str(ObjectId())

        with (
            patch.object(maintenance_module, "get_settings", return_value=_small_settings()),
            patch.object(maintenance_module, "sync_found_caches") as mock_sync,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/maintenance/users/{target_user_id}/found-caches/sync",
                    files={"file": ("found.txt", b"GC" + b"1" * 500, "text/plain")},
                )

        assert response.status_code == 413
        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_within_limit_is_synced(self):
        app = _make_app()
        target_user_id = str(ObjectId())

        with (
            patch.object(maintenance_module, "get_settings", return_value=_small_settings()),
            patch.object(
                maintenance_module,
                "sync_found_caches",
                new=AsyncMock(return_value={"nb_provided": 1, "nb_added": 1, "nb_deleted": 0}),
            ) as mock_sync,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/maintenance/users/{target_user_id}/found-caches/sync",
                    files={"file": ("found.txt", b"GC1234", "text/plain")},
                )

        assert response.status_code == 200
        assert response.json() == {"nb_provided": 1, "nb_added": 1, "nb_deleted": 0}
        mock_sync.assert_awaited_once()
        assert mock_sync.call_args.kwargs["gc_codes"] == ["GC1234"]
        assert str(mock_sync.call_args.kwargs["user_id"]) == target_user_id
