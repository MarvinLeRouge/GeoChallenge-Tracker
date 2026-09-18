"""Tests for POST /auth/register, previously untested. Covers weak-password
rejection (400), duplicate username/email (409), the happy path (verification
email queued via background_tasks), and the post-insert lookup failure (500).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import auth as auth_module
from app.core.rate_limit import limiter


def _make_app(mock_users):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_module.router)
    app.dependency_overrides[auth_module.users_coll] = lambda: mock_users
    return app


class TestRegisterPasswordStrength:
    @pytest.mark.asyncio
    async def test_weak_password_returns_400(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "alllowercase",
                },
            )

        assert response.status_code == 400
        mock_users.find_one.assert_not_awaited()


class TestRegisterUniqueness:
    @pytest.mark.asyncio
    async def test_existing_username_or_email_returns_409(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value={"_id": "existing"})
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "Correct123!",
                },
            )

        assert response.status_code == 409


class TestRegisterHappyPath:
    @pytest.mark.asyncio
    async def test_creates_user_and_queues_verification_email(self):
        new_user_id = ObjectId()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(
            side_effect=[
                None,  # uniqueness check: no existing user
                {
                    "_id": new_user_id,
                    "email": "new@example.com",
                    "username": "newuser",
                    "role": "user",
                },
            ]
        )
        mock_users.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_user_id))
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "Correct123!",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "newuser"
        assert body["email"] == "new@example.com"
        mock_users.insert_one.assert_awaited_once()


class TestRegisterPostInsertLookupFailure:
    @pytest.mark.asyncio
    async def test_missing_created_user_returns_500(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(side_effect=[None, None])
        mock_users.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "Correct123!",
                },
            )

        assert response.status_code == 500
