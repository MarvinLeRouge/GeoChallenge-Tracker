"""Closes the remaining edge-branch gaps on the two admin upload routes: the
generic-exception -> 400 branch on POST /maintenance/upload-gpx, and the
invalid-user_id -> 422 branch on POST /maintenance/users/{user_id}/found-
caches/sync (its size-limit and happy-path behavior is already covered by
test_maintenance_upload_size_limit.py).
"""

from unittest.mock import AsyncMock, patch

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

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


class TestUploadGpxErrorBranch:
    @pytest.mark.asyncio
    async def test_import_failure_is_reported_as_400(self):
        with patch.object(
            maintenance_module,
            "import_gpx_payload",
            new=AsyncMock(side_effect=ValueError("malformed GPX")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/upload-gpx",
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 400
        assert "malformed GPX" in response.json()["detail"]


class TestSyncFoundCachesInvalidUserId:
    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_422(self):
        with patch.object(maintenance_module, "sync_found_caches", new=AsyncMock()) as mock_sync:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/users/not-an-object-id/found-caches/sync",
                    files={"file": ("found.txt", b"GC1234", "text/plain")},
                )

        assert response.status_code == 422
        mock_sync.assert_not_awaited()
