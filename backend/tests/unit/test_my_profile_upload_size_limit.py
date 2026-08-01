"""Tests that POST /my/profile/found-caches/sync enforces the shared upload
size cap (read_upload_file_with_limit), closing the Codecov patch-coverage
gap left by PR #78 (fix/upload-routes-missing-size-cap).

This is the most exposed of the three routes touched by that fix: any
authenticated user can hit it, not just admins. Runs the real route function
against a mocked authenticated user (dependency override) and mocked service
layer, rather than a real MongoDB - keeps this in tests/unit/ while still
exercising the actual route body.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_profile as my_profile_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(my_profile_module.router)

    user = User(
        id=ObjectId(),
        username="regular_user",
        email="user@example.com",
        role="user",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app, user


def _small_settings():
    settings = MagicMock()
    settings.max_upload_bytes = 100
    return settings


class TestSyncMyFoundCachesSizeLimit:
    @pytest.mark.asyncio
    async def test_oversized_file_rejected_before_sync(self):
        app, _ = _make_app()

        with (
            patch.object(my_profile_module, "get_settings", return_value=_small_settings()),
            patch.object(my_profile_module, "sync_found_caches") as mock_sync,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/my/profile/found-caches/sync",
                    files={"file": ("found.txt", b"GC" + b"1" * 500, "text/plain")},
                )

        assert response.status_code == 413
        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_within_limit_is_synced(self):
        app, user = _make_app()

        with (
            patch.object(my_profile_module, "get_settings", return_value=_small_settings()),
            patch.object(
                my_profile_module,
                "sync_found_caches",
                new=AsyncMock(return_value={"nb_provided": 1, "nb_added": 1, "nb_deleted": 0}),
            ) as mock_sync,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/my/profile/found-caches/sync",
                    files={"file": ("found.txt", b"GC1234", "text/plain")},
                )

        assert response.status_code == 200
        assert response.json() == {"nb_provided": 1, "nb_added": 1, "nb_deleted": 0}
        mock_sync.assert_awaited_once()
        assert mock_sync.call_args.kwargs["gc_codes"] == ["GC1234"]
        assert str(mock_sync.call_args.kwargs["user_id"]) == str(user.id)
