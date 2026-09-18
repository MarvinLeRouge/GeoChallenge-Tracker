"""Tests for PUT /my/profile/location, GET /my/profile/location, GET
/my/profile/stats, GET /my/profile, and the decode-error branch of POST
/my/profile/found-caches/sync - none of which had any prior coverage.
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

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app, user


class TestPutMyLocation:
    @pytest.mark.asyncio
    async def test_success_returns_updated_message(self):
        mock_service = MagicMock()
        mock_service.set_user_location = AsyncMock(return_value=None)

        with (
            patch.object(my_profile_module, "get_db", return_value=MagicMock()),
            patch.object(my_profile_module, "UserProfileService", return_value=mock_service),
        ):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put("/my/profile/location", json={"lat": 45.0, "lon": 5.0})

        assert response.status_code == 200
        assert response.json() == {"message": "Location updated successfully"}

    @pytest.mark.asyncio
    async def test_invalid_input_returns_422(self):
        mock_service = MagicMock()
        mock_service.set_user_location = AsyncMock(side_effect=ValueError("Unparseable position"))

        with (
            patch.object(my_profile_module, "get_db", return_value=MagicMock()),
            patch.object(my_profile_module, "UserProfileService", return_value=mock_service),
        ):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    "/my/profile/location", json={"position": "not a position"}
                )

        assert response.status_code == 422
        assert response.json()["detail"] == "Unparseable position"


class TestGetMyLocation:
    @pytest.mark.asyncio
    async def test_found_returns_location(self):
        mock_service = MagicMock()
        mock_service.get_user_location_formatted = AsyncMock(
            return_value={"id": ObjectId(), "lat": 45.0, "lon": 5.0}
        )

        with (
            patch.object(my_profile_module, "get_db", return_value=MagicMock()),
            patch.object(my_profile_module, "UserProfileService", return_value=mock_service),
        ):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/profile/location")

        assert response.status_code == 200
        assert response.json()["lat"] == 45.0

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        mock_service = MagicMock()
        mock_service.get_user_location_formatted = AsyncMock(return_value=None)

        with (
            patch.object(my_profile_module, "get_db", return_value=MagicMock()),
            patch.object(my_profile_module, "UserProfileService", return_value=mock_service),
        ):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/profile/location")

        assert response.status_code == 404


class TestSyncMyFoundCachesDecodeError:
    @pytest.mark.asyncio
    async def test_undecodable_content_returns_400(self):
        app, _ = _make_app()

        bad_content = MagicMock()
        bad_content.decode.side_effect = Exception("cannot decode")

        with patch.object(
            my_profile_module,
            "read_upload_file_with_limit",
            new=AsyncMock(return_value=bad_content),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/my/profile/found-caches/sync",
                    files={"file": ("found.txt", b"GC1234", "text/plain")},
                )

        assert response.status_code == 400
        assert response.json()["detail"] == "Unable to decode file content."


class TestGetMyStats:
    @pytest.mark.asyncio
    async def test_success_returns_stats(self):
        user_id = ObjectId()
        stats = {
            "user_id": user_id,
            "username": "alice",
            "total_caches_found": 10,
            "total_challenges": 2,
            "active_challenges": 1,
            "completed_challenges": 1,
            "created_at": "2026-01-01T00:00:00Z",
        }

        with patch.object(my_profile_module, "get_user_stats", new=AsyncMock(return_value=stats)):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/profile/stats")

        assert response.status_code == 200
        assert response.json()["total_caches_found"] == 10

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(self):
        with patch.object(
            my_profile_module, "get_user_stats", new=AsyncMock(side_effect=ValueError("no user"))
        ):
            app, _ = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/profile/stats")

        assert response.status_code == 404
        assert response.json()["detail"] == "no user"


class TestGetMyProfile:
    @pytest.mark.asyncio
    async def test_returns_current_user(self):
        app, user = _make_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/my/profile")

        assert response.status_code == 200
        assert response.json()["username"] == "alice"
