"""Tests for GET /my/challenges/{uc_id}/progress, POST /my/challenges/{uc_id}/
progress/evaluate, and POST /my/challenges/new/progress - none of which had
any prior coverage. Covers the found/not-found branches of get_progress_route,
the force/non-admin 403 and missing-user-id 400 guards of
evaluate_progress_route, and the default-payload branch of
evaluate_new_progress_route.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_challenge_progress as progress_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(user):
    app = FastAPI()
    app.include_router(progress_module.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _regular_user():
    return User(id=ObjectId(), username="alice", email="alice@example.com", role="user")


def _admin_user():
    return User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")


def _snapshot_doc(uc_id: ObjectId) -> dict:
    return {
        "user_challenge_id": uc_id,
        "checked_at": datetime.now(timezone.utc),
        "aggregate": {
            "percent": 42.0,
            "tasks_done": 3,
            "tasks_total": 7,
            "checked_at": datetime.now(timezone.utc),
        },
        "tasks": [],
    }


class TestGetProgressRoute:
    @pytest.mark.asyncio
    async def test_found_returns_latest_and_history(self):
        uc_id = ObjectId()
        with patch.object(
            progress_module,
            "get_latest_and_history",
            new=AsyncMock(return_value={"latest": None, "history": []}),
        ):
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}/progress")

        assert response.status_code == 200
        assert response.json() == {"latest": None, "history": []}

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        uc_id = ObjectId()
        with patch.object(
            progress_module, "get_latest_and_history", new=AsyncMock(return_value=None)
        ):
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}/progress")

        assert response.status_code == 404


class TestEvaluateProgressRoute:
    @pytest.mark.asyncio
    async def test_force_by_non_admin_returns_403(self):
        uc_id = ObjectId()
        with patch.object(progress_module, "evaluate_progress", new=AsyncMock()) as mock_eval:
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/progress/evaluate", params={"force": "true"}
                )

        assert response.status_code == 403
        mock_eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_force_by_admin_succeeds(self):
        uc_id = ObjectId()
        admin = _admin_user()
        with patch.object(
            progress_module,
            "evaluate_progress",
            new=AsyncMock(return_value=_snapshot_doc(uc_id)),
        ) as mock_eval:
            app = _make_app(admin)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/progress/evaluate", params={"force": "true"}
                )

        assert response.status_code == 200
        mock_eval.assert_awaited_once()
        assert mock_eval.call_args.kwargs["force"] is True

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_400(self):
        uc_id = ObjectId()
        user_without_id = User(id=None, username="ghost", email="ghost@example.com", role="user")
        with patch.object(progress_module, "evaluate_progress", new=AsyncMock()) as mock_eval:
            app = _make_app(user_without_id)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/my/challenges/{uc_id}/progress/evaluate")

        assert response.status_code == 400
        mock_eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_regular_user_without_force_succeeds(self):
        uc_id = ObjectId()
        with patch.object(
            progress_module,
            "evaluate_progress",
            new=AsyncMock(return_value=_snapshot_doc(uc_id)),
        ):
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/my/challenges/{uc_id}/progress/evaluate")

        assert response.status_code == 200
        body = response.json()
        assert body["aggregate"]["percent"] == 42.0


class TestEvaluateNewProgressRoute:
    @pytest.mark.asyncio
    async def test_empty_payload_uses_defaults(self):
        with patch.object(
            progress_module,
            "evaluate_new_progress",
            new=AsyncMock(return_value={"created": 2, "skipped": 0}),
        ) as mock_eval:
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/my/challenges/new/progress", json={})

        assert response.status_code == 200
        assert response.json() == {"created": 2, "skipped": 0}
        assert mock_eval.call_args.kwargs["include_pending"] is False
        assert mock_eval.call_args.kwargs["limit"] == 50

    @pytest.mark.asyncio
    async def test_explicit_payload_is_passed_through(self):
        with patch.object(
            progress_module,
            "evaluate_new_progress",
            new=AsyncMock(return_value={"created": 5, "skipped": 1}),
        ) as mock_eval:
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/my/challenges/new/progress",
                    json={"include_pending": True, "limit": 10},
                )

        assert response.status_code == 200
        assert mock_eval.call_args.kwargs["include_pending"] is True
        assert mock_eval.call_args.kwargs["limit"] == 10
