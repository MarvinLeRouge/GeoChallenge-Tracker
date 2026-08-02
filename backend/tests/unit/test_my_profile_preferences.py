"""Tests for PATCH /my/profile/preferences.

Runs the real route function against a mocked authenticated user (dependency
override) and a mocked database, rather than a real MongoDB - keeps this in
tests/unit/ while still exercising the actual route body.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_profile as my_profile_module
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(user_id: ObjectId):
    app = FastAPI()
    app.include_router(my_profile_module.router)

    user = User(
        id=PyObjectId(user_id), username="regular_user", email="user@example.com", role="user"
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _make_mock_db(user_id: ObjectId, stored_after_update: dict):
    mock_users = AsyncMock()
    mock_users.update_one = AsyncMock(return_value=MagicMock())
    mock_users.find_one = AsyncMock(return_value={"_id": user_id, **stored_after_update})
    mock_db = MagicMock()
    mock_db.users = mock_users
    return mock_db, mock_users


class TestPatchMyPreferences:
    @pytest.mark.asyncio
    async def test_updates_dark_mode_and_returns_updated_profile(self):
        user_id = ObjectId()
        mock_db, mock_users = _make_mock_db(
            user_id,
            {
                "username": "regular_user",
                "email": "user@example.com",
                "role": "user",
                "preferences": {"language": "fr", "dark_mode": True},
            },
        )

        with patch.object(my_profile_module, "get_db", return_value=mock_db):
            app = _make_app(user_id)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch("/my/profile/preferences", json={"dark_mode": True})

        assert response.status_code == 200
        body = response.json()
        assert body["preferences"]["dark_mode"] is True
        mock_users.update_one.assert_awaited_once()
        set_fields = mock_users.update_one.call_args[0][1]["$set"]
        assert set_fields["preferences.dark_mode"] is True
        assert "preferences.language" not in set_fields

    @pytest.mark.asyncio
    async def test_returns_404_if_user_vanished_after_update(self):
        user_id = ObjectId()
        mock_users = AsyncMock()
        mock_users.update_one = AsyncMock(return_value=MagicMock())
        mock_users.find_one = AsyncMock(return_value=None)
        mock_db = MagicMock()
        mock_db.users = mock_users

        with patch.object(my_profile_module, "get_db", return_value=mock_db):
            app = _make_app(user_id)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch("/my/profile/preferences", json={"dark_mode": True})

        assert response.status_code == 404
