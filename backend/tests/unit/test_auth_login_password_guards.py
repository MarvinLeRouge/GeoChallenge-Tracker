"""Login and register guards around password hashing: size cap, unusable stored hashes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.routes import auth as auth_module
from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limit import limiter
from app.domain.models.user import PASSWORD_MAX_LENGTH, UserInRegister


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    # the login limit (10/minute) is shared by every test in the process
    limiter.reset()


def _make_app(user):
    app = FastAPI()
    app.state.limiter = limiter
    register_exception_handlers(app)
    app.include_router(auth_module.router)
    users = AsyncMock()
    users.find_one = AsyncMock(return_value=user)
    app.dependency_overrides[auth_module.users_coll] = lambda: users
    return app


def test_register_accepts_the_max_length():
    UserInRegister(username="alice", email="a@example.com", password="Aa1!" * 32)


def test_register_rejects_a_longer_password():
    with pytest.raises(ValidationError) as exc_info:
        UserInRegister(
            username="alice", email="a@example.com", password="A" * (PASSWORD_MAX_LENGTH + 1)
        )
    assert exc_info.value.errors()[0]["type"] == "string_too_long"


@pytest.mark.asyncio
async def test_login_with_an_oversized_password_skips_hashing():
    app = _make_app({"_id": "507f1f77bcf86cd799439011", "password_hash": "$argon2id$x"})
    with patch.object(auth_module, "verify_password") as verify:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/login",
                data={"username": "alice", "password": "x" * 100_000},
            )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    verify.assert_not_called()


@pytest.mark.parametrize("stored_hash", [None, "", "not-a-known-hash", "$2b$12$broken"])
@pytest.mark.asyncio
async def test_login_with_a_missing_or_unusable_hash_returns_401(stored_hash):
    user = {"_id": "507f1f77bcf86cd799439011", "is_verified": True}
    if stored_hash is not None:
        user["password_hash"] = stored_hash
    app = _make_app(user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/auth/login", data={"username": "alice", "password": "Secure123!"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
