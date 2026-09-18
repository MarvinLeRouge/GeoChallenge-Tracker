"""Tests for POST /challenges/refresh-from-caches, previously entirely
untested. Covers the default (no cache_ids) branch, the explicit cache_ids
branch, and the admin-only guard.
"""

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import challenges as challenges_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(user):
    app = FastAPI()
    app.include_router(challenges_module.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _admin_user():
    return User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")


def _regular_user():
    return User(id=ObjectId(), username="alice", email="alice@example.com", role="user")


class TestRefreshFromCaches:
    @pytest.mark.asyncio
    async def test_no_cache_ids_scans_entire_collection(self):
        with patch.object(
            challenges_module,
            "create_challenges_from_caches",
            new=AsyncMock(return_value={"created": 3, "updated": 1}),
        ) as mock_create:
            app = _make_app(_admin_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/challenges/refresh-from-caches", json={})

        assert response.status_code == 200
        assert response.json() == {"ok": True, "stats": {"created": 3, "updated": 1}}
        mock_create.assert_awaited_once_with(cache_ids=None)

    @pytest.mark.asyncio
    async def test_explicit_cache_ids_are_converted(self):
        cache_id = ObjectId()
        with patch.object(
            challenges_module,
            "create_challenges_from_caches",
            new=AsyncMock(return_value={"created": 1, "updated": 0}),
        ) as mock_create:
            app = _make_app(_admin_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/challenges/refresh-from-caches", json={"cache_ids": [str(cache_id)]}
                )

        assert response.status_code == 200
        mock_create.assert_awaited_once_with(cache_ids=[cache_id])

    @pytest.mark.asyncio
    async def test_non_admin_is_rejected(self):
        with patch.object(
            challenges_module, "create_challenges_from_caches", new=AsyncMock()
        ) as mock_create:
            app = _make_app(_regular_user())
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/challenges/refresh-from-caches", json={})

        assert response.status_code == 403
        mock_create.assert_not_awaited()
