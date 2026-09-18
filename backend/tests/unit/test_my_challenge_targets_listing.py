"""Tests for GET /my/challenges/{uc_id}/targets, GET /my/challenges/{uc_id}/
targets/nearby, GET /my/targets, and GET /my/targets/nearby - none of which
had any prior coverage. Covers the saved-location fallback shared by both
"nearby" routes (success and the 422 no-location guard).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_challenge_targets as targets_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(targets_module.router)

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _empty_list_response():
    return {"items": [], "nb_items": 0, "page": 1, "page_size": 50, "nb_pages": 0}


class TestListTargetsUc:
    @pytest.mark.asyncio
    async def test_delegates_with_pagination_and_sort(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module,
            "list_targets_for_user_challenge",
            new=AsyncMock(return_value=_empty_list_response()),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/my/challenges/{uc_id}/targets", params={"page": 2, "sort": "GC"}
                )

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["page"] == 2
        assert mock_list.call_args.kwargs["sort"] == "GC"


class TestListTargetsUcNearby:
    @pytest.mark.asyncio
    async def test_explicit_lat_lon(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module,
            "list_targets_nearby_for_user_challenge",
            new=AsyncMock(return_value=_empty_list_response()),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/my/challenges/{uc_id}/targets/nearby",
                    params={"lat": 45.0, "lon": 5.0},
                )

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["lat"] == 45.0
        assert mock_list.call_args.kwargs["lon"] == 5.0

    @pytest.mark.asyncio
    async def test_falls_back_to_saved_location(self):
        uc_id = ObjectId()
        mock_profile_service = MagicMock()
        mock_profile_service.get_user_location = AsyncMock(
            return_value={"coordinates": [5.0, 45.0]}
        )

        with (
            patch.object(targets_module, "get_db", return_value=MagicMock()),
            patch.object(targets_module, "UserProfileService", return_value=mock_profile_service),
            patch.object(
                targets_module,
                "list_targets_nearby_for_user_challenge",
                new=AsyncMock(return_value=_empty_list_response()),
            ) as mock_list,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}/targets/nearby")

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["lat"] == 45.0
        assert mock_list.call_args.kwargs["lon"] == 5.0

    @pytest.mark.asyncio
    async def test_no_saved_location_returns_422(self):
        uc_id = ObjectId()
        mock_profile_service = MagicMock()
        mock_profile_service.get_user_location = AsyncMock(return_value=None)

        with (
            patch.object(targets_module, "get_db", return_value=MagicMock()),
            patch.object(targets_module, "UserProfileService", return_value=mock_profile_service),
            patch.object(
                targets_module, "list_targets_nearby_for_user_challenge", new=AsyncMock()
            ) as mock_list,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}/targets/nearby")

        assert response.status_code == 422
        mock_list.assert_not_awaited()


class TestListTargetsAll:
    @pytest.mark.asyncio
    async def test_delegates_with_status_filter(self):
        with patch.object(
            targets_module,
            "list_targets_for_user",
            new=AsyncMock(return_value=_empty_list_response()),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets", params={"status_filter": "accepted"})

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["status_filter"] == "accepted"

    @pytest.mark.asyncio
    async def test_no_status_filter_passes_none(self):
        with patch.object(
            targets_module,
            "list_targets_for_user",
            new=AsyncMock(return_value=_empty_list_response()),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets")

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["status_filter"] is None


class TestListTargetsAllNearby:
    @pytest.mark.asyncio
    async def test_explicit_lat_lon(self):
        with patch.object(
            targets_module,
            "list_targets_nearby_for_user",
            new=AsyncMock(return_value=_empty_list_response()),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets/nearby", params={"lat": 45.0, "lon": 5.0})

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["lat"] == 45.0

    @pytest.mark.asyncio
    async def test_falls_back_to_saved_location(self):
        mock_profile_service = MagicMock()
        mock_profile_service.get_user_location = AsyncMock(
            return_value={"coordinates": [5.0, 45.0]}
        )

        with (
            patch.object(targets_module, "get_db", return_value=MagicMock()),
            patch.object(targets_module, "UserProfileService", return_value=mock_profile_service),
            patch.object(
                targets_module,
                "list_targets_nearby_for_user",
                new=AsyncMock(return_value=_empty_list_response()),
            ) as mock_list,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets/nearby")

        assert response.status_code == 200
        assert mock_list.call_args.kwargs["lat"] == 45.0
        assert mock_list.call_args.kwargs["lon"] == 5.0

    @pytest.mark.asyncio
    async def test_no_saved_location_returns_422(self):
        mock_profile_service = MagicMock()
        mock_profile_service.get_user_location = AsyncMock(return_value=None)

        with (
            patch.object(targets_module, "get_db", return_value=MagicMock()),
            patch.object(targets_module, "UserProfileService", return_value=mock_profile_service),
            patch.object(
                targets_module, "list_targets_nearby_for_user", new=AsyncMock()
            ) as mock_list,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets/nearby")

        assert response.status_code == 422
        mock_list.assert_not_awaited()
