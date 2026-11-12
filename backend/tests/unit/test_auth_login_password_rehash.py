"""Tests that /auth/login transparently upgrades legacy bcrypt password hashes
to argon2id on successful login, and leaves already-current hashes untouched.

Runs the real login() route against a mocked users collection via FastAPI's
dependency override, rather than a real MongoDB - keeps this in tests/unit/
while still exercising the actual route body.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import auth as auth_module
from app.core.rate_limit import limiter
from app.core.security import hash_password
from tests.unit import legacy_passlib_hashes as legacy


def _make_app(password_hash: str):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_module.router)

    mock_users = AsyncMock()
    mock_users.find_one = AsyncMock(
        return_value={
            "_id": "507f1f77bcf86cd799439011",
            "password_hash": password_hash,
            "is_verified": True,
        }
    )
    app.dependency_overrides[auth_module.users_coll] = lambda: mock_users
    return app, mock_users


class TestLoginPasswordRehash:
    @pytest.mark.asyncio
    async def test_legacy_bcrypt_hash_is_upgraded_to_argon2id(self):
        app, mock_users = _make_app(password_hash=legacy.BCRYPT_HASH)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                data={"username": "user", "password": legacy.PASSWORD},
            )

        assert response.status_code == 200
        mock_users.update_one.assert_awaited_once()
        call = mock_users.update_one.call_args
        assert call.args[0] == {"_id": "507f1f77bcf86cd799439011"}
        new_hash = call.args[1]["$set"]["password_hash"]
        assert new_hash.startswith("$argon2id$")

    @pytest.mark.asyncio
    async def test_legacy_passlib_argon2_hash_is_not_rewritten(self):
        app, mock_users = _make_app(password_hash=legacy.ARGON2_HASH)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                data={"username": "user", "password": legacy.PASSWORD},
            )

        assert response.status_code == 200
        mock_users.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_current_argon2_hash_is_not_rewritten(self):
        current_hash = hash_password("Correct123!")
        app, mock_users = _make_app(password_hash=current_hash)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                data={"username": "user", "password": "Correct123!"},
            )

        assert response.status_code == 200
        mock_users.update_one.assert_not_awaited()
