"""Tests for the remaining POST /auth/login branches (success path, missing
credentials, JSON body variant, malformed JSON body), and for POST /auth/
refresh and POST /auth/logout - none of which had any coverage yet (only the
rehash and security-logging branches of login were previously tested).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import auth as auth_module
from app.core.rate_limit import limiter
from app.core.security import create_refresh_token, hash_password


def _make_app(mock_users):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_module.router)
    app.dependency_overrides[auth_module.users_coll] = lambda: mock_users
    return app


class TestLoginMissingCredentials:
    @pytest.mark.asyncio
    async def test_missing_password_returns_422(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/login", data={"username": "someone"})

        assert response.status_code == 422
        mock_users.find_one.assert_not_awaited()


class TestLoginJsonBody:
    @pytest.mark.asyncio
    async def test_json_body_with_email_field_logs_in(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "password_hash": hash_password("Correct123!"),
                "is_verified": True,
            }
        )
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "Correct123!"},
            )

        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_malformed_json_body_is_treated_as_missing_credentials(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                content=b"not-json",
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 422


class TestLoginHappyPath:
    @pytest.mark.asyncio
    async def test_verified_user_receives_access_token_and_refresh_cookie(self):
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(
            return_value={
                "_id": "507f1f77bcf86cd799439011",
                "password_hash": hash_password("Correct123!"),
                "is_verified": True,
            }
        )
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                data={"username": "user", "password": "Correct123!"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert "access_token" in body
        assert "refresh_token=" in response.headers.get("set-cookie", "")


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_no_cookie_returns_401(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "No refresh token"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", "not-a-valid-jwt")
            response = await client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    @pytest.mark.asyncio
    async def test_valid_token_for_inactive_user_returns_401(self, monkeypatch):
        from bson import ObjectId

        user_id = ObjectId()
        token = create_refresh_token(data={"sub": str(user_id)})

        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=None)
        app = _make_app(mock_users)

        monkeypatch.setattr(auth_module, "is_refresh_token_revoked", AsyncMock(return_value=False))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", token)
            response = await client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    @pytest.mark.asyncio
    async def test_valid_token_for_active_user_returns_new_access_token(self, monkeypatch):
        from bson import ObjectId

        user_id = ObjectId()
        token = create_refresh_token(data={"sub": str(user_id)})

        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value={"_id": user_id, "is_active": True})
        app = _make_app(mock_users)

        monkeypatch.setattr(auth_module, "is_refresh_token_revoked", AsyncMock(return_value=False))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", token)
            response = await client.post("/auth/refresh")

        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_revoked_jti_returns_401(self, monkeypatch):
        from bson import ObjectId

        user_id = ObjectId()
        token = create_refresh_token(data={"sub": str(user_id)})

        mock_users = AsyncMock()
        app = _make_app(mock_users)

        monkeypatch.setattr(auth_module, "is_refresh_token_revoked", AsyncMock(return_value=True))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", token)
            response = await client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"
        mock_users.find_one.assert_not_awaited()


class TestLogout:
    @pytest.mark.asyncio
    async def test_without_cookie_still_succeeds(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/logout")

        assert response.status_code == 200
        assert response.json() == {"message": "Logged out"}

    @pytest.mark.asyncio
    async def test_invalid_cookie_is_ignored(self):
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", "not-a-valid-jwt")
            response = await client.post("/auth/logout")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_cookie_revokes_token(self, monkeypatch):
        token = create_refresh_token(data={"sub": "507f1f77bcf86cd799439011"})
        mock_users = AsyncMock()
        app = _make_app(mock_users)

        mock_revoke = AsyncMock()
        monkeypatch.setattr(auth_module, "revoke_refresh_token", mock_revoke)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", token)
            response = await client.post("/auth/logout")

        assert response.status_code == 200
        mock_revoke.assert_awaited_once()
