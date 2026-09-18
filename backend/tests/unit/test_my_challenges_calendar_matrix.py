"""Tests for GET /my/challenges/basics/calendar and GET /my/challenges/basics/
matrix - neither had any prior coverage. Covers the filter passthrough and
service delegation for both routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_challenges as my_challenges_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(my_challenges_module.router)

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _calendar_result() -> dict:
    return {
        "completed_days_365": 10,
        "completion_rate_365": 0.03,
        "completed_days_366": 10,
        "completion_rate_366": 0.03,
        "missing_days": [],
        "missing_days_by_month": {},
        "completed_days": [],
    }


def _matrix_result() -> dict:
    return {
        "completed_combinations_count": 5,
        "completion_rate": 0.06,
        "next_round_completed_count": 0,
        "next_round_completion_rate": 0.0,
        "missing_combinations": [],
        "missing_combinations_by_difficulty": {},
        "completed_combinations_details": [],
    }


class TestVerifyCalendar:
    @pytest.mark.asyncio
    async def test_delegates_with_filters(self):
        mock_service = MagicMock()
        mock_service.verify_user_calendar = AsyncMock(return_value=_calendar_result())

        with (
            patch.object(my_challenges_module, "get_db", return_value=MagicMock()),
            patch.object(
                my_challenges_module, "CalendarVerificationService", return_value=mock_service
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/my/challenges/basics/calendar",
                    params={"cache_type": "Traditional", "cache_size": "Regular"},
                )

        assert response.status_code == 200
        assert response.json()["completed_days_365"] == 10
        mock_service.verify_user_calendar.assert_awaited_once()
        filters = mock_service.verify_user_calendar.call_args.args[1]
        assert filters.cache_type_name == "Traditional"
        assert filters.cache_size_name == "Regular"


class TestVerifyMatrix:
    @pytest.mark.asyncio
    async def test_delegates_without_filters(self):
        mock_service = MagicMock()
        mock_service.verify_user_matrix = AsyncMock(return_value=_matrix_result())

        with (
            patch.object(my_challenges_module, "get_db", return_value=MagicMock()),
            patch.object(
                my_challenges_module, "MatrixVerificationService", return_value=mock_service
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/my/challenges/basics/matrix")

        assert response.status_code == 200
        assert response.json()["completed_combinations_count"] == 5
        filters = mock_service.verify_user_matrix.call_args.args[1]
        assert filters.cache_type_name is None
        assert filters.cache_size_name is None
