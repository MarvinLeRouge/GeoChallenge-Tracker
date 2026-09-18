"""Tests for GET /my/challenges/{uc_id} and PATCH /my/challenges/{uc_id} -
none of which had any prior coverage. Covers the found/not-found branches of
get_uc, and the success/failure/not-found branches of patch_uc.
"""

from unittest.mock import AsyncMock, patch

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


def _detail_doc(uc_id: ObjectId) -> dict:
    return {
        "id": uc_id,
        "status": "accepted",
        "effective_status": "accepted",
        "challenge": {"id": ObjectId(), "name": "Test challenge"},
        "cache": {"id": ObjectId(), "GC": "GC12345"},
    }


class TestGetUc:
    @pytest.mark.asyncio
    async def test_found_returns_detail(self):
        uc_id = ObjectId()
        with patch.object(
            my_challenges_module,
            "get_user_challenge_detail",
            new=AsyncMock(return_value=_detail_doc(uc_id)),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(uc_id)

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        uc_id = ObjectId()
        with patch.object(
            my_challenges_module, "get_user_challenge_detail", new=AsyncMock(return_value=None)
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}")

        assert response.status_code == 404


class TestPatchUc:
    @pytest.mark.asyncio
    async def test_success_returns_updated_uc(self):
        uc_id = ObjectId()
        updated = {"id": uc_id, "status": "completed", "effective_status": "completed"}
        with patch.object(
            my_challenges_module,
            "patch_user_challenge",
            new=AsyncMock(return_value=(True, None, updated)),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/my/challenges/{uc_id}", json={"status": "completed"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_failure_returns_400(self):
        uc_id = ObjectId()
        with patch.object(
            my_challenges_module,
            "patch_user_challenge",
            new=AsyncMock(return_value=(False, "Invalid status transition", None)),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/my/challenges/{uc_id}", json={"status": "completed"}
                )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid status transition"

    @pytest.mark.asyncio
    async def test_success_but_no_doc_returns_404(self):
        uc_id = ObjectId()
        with patch.object(
            my_challenges_module,
            "patch_user_challenge",
            new=AsyncMock(return_value=(True, None, None)),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    f"/my/challenges/{uc_id}", json={"status": "completed"}
                )

        assert response.status_code == 404
