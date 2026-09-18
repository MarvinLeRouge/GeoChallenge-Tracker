"""Tests for POST /maintenance/users/{user_id}/targets/evaluate-all and GET
/maintenance/users/{user_id}/stats, previously uncovered - including the
invalid-ObjectId (422) and not-found (404) branches shared by both routes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dto.user_stats import UserStatsOut
from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


class TestEvaluateAllTargets:
    @pytest.mark.asyncio
    async def test_valid_user_id_triggers_forced_evaluation(self):
        target_user_id = ObjectId()

        with patch.object(
            maintenance_module,
            "evaluate_all_for_user",
            new=AsyncMock(return_value={"ok": True, "evaluated": 2}),
        ) as mock_evaluate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/maintenance/users/{target_user_id}/targets/evaluate-all"
                )

        assert response.status_code == 200
        assert response.json() == {"ok": True, "evaluated": 2}
        mock_evaluate.assert_awaited_once_with(user_id=target_user_id, force=True)

    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_422(self):
        with patch.object(
            maintenance_module, "evaluate_all_for_user", new=AsyncMock()
        ) as mock_evaluate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/users/not-an-object-id/targets/evaluate-all"
                )

        assert response.status_code == 422
        mock_evaluate.assert_not_awaited()


class TestMaintenanceGetUserStats:
    @pytest.mark.asyncio
    async def test_valid_user_id_returns_stats(self):
        target_user_id = ObjectId()
        stats = UserStatsOut(
            user_id=target_user_id,
            username="alice",
            total_caches_found=5,
            total_challenges=2,
            active_challenges=1,
            completed_challenges=1,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        with patch.object(
            maintenance_module, "get_user_stats", new=AsyncMock(return_value=stats)
        ) as mock_get_stats:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/maintenance/users/{target_user_id}/stats")

        assert response.status_code == 200
        assert response.json()["username"] == "alice"
        mock_get_stats.assert_awaited_once_with(
            user_id=target_user_id, target_user_id=target_user_id
        )

    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_422(self):
        with patch.object(maintenance_module, "get_user_stats", new=AsyncMock()) as mock_get_stats:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/users/not-an-object-id/stats")

        assert response.status_code == 422
        mock_get_stats.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(self):
        target_user_id = ObjectId()

        with patch.object(
            maintenance_module,
            "get_user_stats",
            new=AsyncMock(side_effect=ValueError("User not found")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/maintenance/users/{target_user_id}/stats")

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"
