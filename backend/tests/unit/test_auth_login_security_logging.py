"""Tests that failed /auth/login attempts are recorded by the security logger.

Runs the real login() route (rate limiter included) against a mocked users
collection via FastAPI's dependency override, rather than a real MongoDB - keeps
this in tests/unit/ while still exercising the actual route body, not just a
hand-mocked Request.
"""

import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import auth as auth_module
from app.core.rate_limit import limiter


def _make_app(users_find_one_return):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_module.router)

    mock_users = AsyncMock()
    mock_users.find_one = AsyncMock(return_value=users_find_one_return)
    app.dependency_overrides[auth_module.users_coll] = lambda: mock_users
    return app


class TestLoginSecurityLogging:
    @pytest.mark.asyncio
    async def test_invalid_credentials_logs_a_warning(self, caplog):
        app = _make_app(users_find_one_return=None)  # no such user

        with caplog.at_level(logging.WARNING, logger="geocaching.security"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/auth/login",
                    data={"username": "nosuchuser", "password": "whatever"},
                )

        assert response.status_code == 401
        assert len(caplog.records) == 1
        assert "Failed login attempt" in caplog.records[0].message
        assert "nosuchuser" in caplog.records[0].message
        # The password must never be logged.
        assert "whatever" not in caplog.records[0].message

    @pytest.mark.asyncio
    async def test_unverified_account_logs_an_info(self, caplog):
        from app.core.security import hash_password

        app = _make_app(
            users_find_one_return={
                "_id": "507f1f77bcf86cd799439011",
                "password_hash": hash_password("Correct123!"),
                "is_verified": False,
            }
        )

        with caplog.at_level(logging.INFO, logger="geocaching.security"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/auth/login",
                    data={"username": "unverifieduser", "password": "Correct123!"},
                )

        assert response.status_code == 401
        assert len(caplog.records) == 1
        assert "unverified account" in caplog.records[0].message.lower()
        assert "unverifieduser" in caplog.records[0].message
