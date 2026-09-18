"""Tests for POST /my/challenges/{uc_id}/targets/evaluate, POST /my/targets/
evaluate-all, GET /my/targets/refresh-status, and DELETE /my/challenges/{uc_id}
/targets - none of which had any prior coverage. Covers the geo-filter
fallback-to-saved-location branch (success and the 422 no-location/no-radius
guards) on evaluate_targets.
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


class TestEvaluateTargetsNoGeoFilter:
    @pytest.mark.asyncio
    async def test_delegates_with_no_geo_context(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module,
            "evaluate_targets_for_user_challenge",
            new=AsyncMock(return_value={"ok": True, "inserted": 3, "updated": 0, "total": 3}),
        ) as mock_evaluate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/my/challenges/{uc_id}/targets/evaluate")

        assert response.status_code == 200
        assert response.json() == {"ok": True, "inserted": 3, "updated": 0, "total": 3}
        mock_evaluate.assert_awaited_once()
        assert mock_evaluate.call_args.kwargs["geo_ctx"] is None


class TestEvaluateTargetsWithGeoFilter:
    @pytest.mark.asyncio
    async def test_explicit_lat_lon_and_radius(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module,
            "evaluate_targets_for_user_challenge",
            new=AsyncMock(return_value={"ok": True, "inserted": 1, "updated": 0, "total": 1}),
        ) as mock_evaluate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/targets/evaluate",
                    params={
                        "include_geo_filter": "true",
                        "lat": 45.0,
                        "lon": 5.0,
                        "radius_km": 10,
                    },
                )

        assert response.status_code == 200
        assert mock_evaluate.call_args.kwargs["geo_ctx"] == {
            "lat": 45.0,
            "lon": 5.0,
            "radius_km": 10.0,
        }

    @pytest.mark.asyncio
    async def test_missing_radius_km_returns_422(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module, "evaluate_targets_for_user_challenge", new=AsyncMock()
        ) as mock_evaluate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/targets/evaluate",
                    params={"include_geo_filter": "true", "lat": 45.0, "lon": 5.0},
                )

        assert response.status_code == 422
        mock_evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_saved_location_when_lat_lon_absent(self):
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
                "evaluate_targets_for_user_challenge",
                new=AsyncMock(return_value={"ok": True, "inserted": 0, "updated": 0, "total": 0}),
            ) as mock_evaluate,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/targets/evaluate",
                    params={"include_geo_filter": "true", "radius_km": 10},
                )

        assert response.status_code == 200
        assert mock_evaluate.call_args.kwargs["geo_ctx"] == {
            "lat": 45.0,
            "lon": 5.0,
            "radius_km": 10.0,
        }

    @pytest.mark.asyncio
    async def test_no_saved_location_returns_422(self):
        uc_id = ObjectId()
        mock_profile_service = MagicMock()
        mock_profile_service.get_user_location = AsyncMock(return_value=None)

        with (
            patch.object(targets_module, "get_db", return_value=MagicMock()),
            patch.object(targets_module, "UserProfileService", return_value=mock_profile_service),
            patch.object(
                targets_module, "evaluate_targets_for_user_challenge", new=AsyncMock()
            ) as mock_evaluate,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/targets/evaluate",
                    params={"include_geo_filter": "true", "radius_km": 10},
                )

        assert response.status_code == 422
        mock_evaluate.assert_not_awaited()


class TestEvaluateAllTargets:
    @pytest.mark.asyncio
    async def test_delegates_with_force_false(self):
        with patch.object(
            targets_module,
            "evaluate_all_for_user",
            new=AsyncMock(return_value={"ok": True, "evaluated": 2}),
        ) as mock_evaluate_all:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/my/targets/evaluate-all")

        assert response.status_code == 200
        assert response.json() == {"ok": True, "evaluated": 2}
        mock_evaluate_all.assert_awaited_once()
        assert mock_evaluate_all.call_args.kwargs["force"] is False


class TestTargetsRefreshStatus:
    @pytest.mark.asyncio
    async def test_returns_service_result(self):
        with patch.object(
            targets_module,
            "get_targets_refresh_status",
            new=AsyncMock(return_value={"needs_refresh": True}),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/targets/refresh-status")

        assert response.status_code == 200
        assert response.json() == {"needs_refresh": True}


class TestClearTargetsUc:
    @pytest.mark.asyncio
    async def test_deletes_targets_for_challenge(self):
        uc_id = ObjectId()
        with patch.object(
            targets_module,
            "delete_targets_for_user_challenge",
            new=AsyncMock(return_value={"ok": True, "deleted": 5}),
        ) as mock_delete:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete(f"/my/challenges/{uc_id}/targets")

        assert response.status_code == 200
        assert response.json() == {"ok": True, "deleted": 5}
        mock_delete.assert_awaited_once()
