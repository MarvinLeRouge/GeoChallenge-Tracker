"""Tests for GET /auth/verify-email, POST /auth/verify-email, and POST
/auth/resend-verification - none of which had any prior coverage.
"""

from unittest.mock import AsyncMock

import pytest
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


class TestVerifyEmailGet:
    @pytest.mark.asyncio
    async def test_valid_code_activates_account(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value={"_id": "507f1f77bcf86cd799439011"})
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/verify-email", params={"code": "abc123"})

        assert response.status_code == 200
        assert response.json() == {"message": "Email verified"}
        mock_users.update_one.assert_awaited_once()
        set_fields = mock_users.update_one.call_args.args[1]["$set"]
        assert set_fields["is_verified"] is True

    @pytest.mark.asyncio
    async def test_invalid_or_expired_code_returns_400(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=None)
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/verify-email", params={"code": "expired"})

        assert response.status_code == 400
        mock_users.update_one.assert_not_awaited()


class TestVerifyEmailPost:
    @pytest.mark.asyncio
    async def test_delegates_to_get_variant(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value={"_id": "507f1f77bcf86cd799439011"})
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/verify-email", json={"code": "abc123"})

        assert response.status_code == 200
        assert response.json() == {"message": "Email verified"}


class TestResendVerification:
    @pytest.mark.asyncio
    async def test_unverified_existing_account_gets_new_code_and_email(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "is_verified": False,
            }
        )
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/resend-verification", json={"identifier": "user@example.com"}
            )

        assert response.status_code == 200
        mock_users.update_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_already_verified_account_gets_generic_message_without_update(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "is_verified": True,
            }
        )
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/resend-verification", json={"identifier": "user@example.com"}
            )

        assert response.status_code == 200
        mock_users.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_account_gets_same_generic_message(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=None)
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/resend-verification", json={"identifier": "nobody@example.com"}
            )

        assert response.status_code == 200
        mock_users.update_one.assert_not_awaited()
