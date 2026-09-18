"""Tests for POST /my/challenges/sync, GET /my/challenges, and PATCH
/my/challenges (batch patch) - none of which had any prior coverage. Covers
the batch guard branches (empty list, oversized batch) and the per-item
success/not-found/HTTPException/generic-exception branches of patch_uc_batch.
"""

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
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


class TestSync:
    @pytest.mark.asyncio
    async def test_returns_sync_stats(self):
        with patch.object(
            my_challenges_module,
            "sync_user_challenges",
            new=AsyncMock(return_value={"created": 3, "skipped": 1}),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/my/challenges/sync")

        assert response.status_code == 200
        assert response.json() == {"created": 3, "skipped": 1}


class TestListUc:
    @pytest.mark.asyncio
    async def test_delegates_with_status_and_pagination(self):
        empty_response = {"items": [], "nb_items": 0, "page": 2, "page_size": 10, "nb_pages": 0}
        with patch.object(
            my_challenges_module,
            "list_user_challenges",
            new=AsyncMock(return_value=empty_response),
        ) as mock_list:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/my/challenges", params={"status": "accepted", "page": 2, "page_size": 10}
                )

        assert response.status_code == 200
        assert response.json()["page"] == 2
        args = mock_list.call_args.args
        assert args[1] == "accepted"
        assert args[2] == 2
        assert args[3] == 10


class TestPatchUcBatchEmptyAndOversized:
    @pytest.mark.asyncio
    async def test_empty_items_returns_zeroed_response(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/my/challenges", json=[])

        assert response.status_code == 200
        assert response.json() == {"updated_count": 0, "total": 0, "results": []}

    @pytest.mark.asyncio
    async def test_oversized_batch_returns_413(self):
        items = [{"uc_id": str(ObjectId())} for _ in range(201)]
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/my/challenges", json=items)

        assert response.status_code == 413


class TestPatchUcBatchItemOutcomes:
    @pytest.mark.asyncio
    async def test_mixed_success_and_not_found(self):
        uc_id_ok = ObjectId()
        uc_id_missing = ObjectId()
        items = [{"uc_id": str(uc_id_ok)}, {"uc_id": str(uc_id_missing)}]

        async def _fake_patch(user_id, uc_id, patch_data):
            if uc_id == uc_id_ok:
                return True, None, {"id": uc_id_ok, "status": "accepted"}
            return False, None, None

        with patch.object(
            my_challenges_module, "patch_user_challenge", new=AsyncMock(side_effect=_fake_patch)
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch("/my/challenges", json=items)

        assert response.status_code == 200
        body = response.json()
        assert body["updated_count"] == 1
        assert body["total"] == 2
        assert body["results"][0]["ok"] is True
        assert body["results"][1]["ok"] is False
        assert body["results"][1]["error"] == "UserChallenge not found"

    @pytest.mark.asyncio
    async def test_http_exception_is_captured_as_itemized_result(self):
        items = [{"uc_id": str(ObjectId())}]

        with patch.object(
            my_challenges_module,
            "patch_user_challenge",
            new=AsyncMock(side_effect=HTTPException(status_code=400, detail="Invalid status")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch("/my/challenges", json=items)

        assert response.status_code == 200
        body = response.json()
        assert body["updated_count"] == 0
        assert body["results"][0]["ok"] is False
        assert body["results"][0]["error"] == "Invalid status"

    @pytest.mark.asyncio
    async def test_generic_exception_is_captured_as_itemized_result(self):
        items = [{"uc_id": str(ObjectId())}]

        with patch.object(
            my_challenges_module,
            "patch_user_challenge",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch("/my/challenges", json=items)

        assert response.status_code == 200
        body = response.json()
        assert body["updated_count"] == 0
        assert body["results"][0]["ok"] is False
        assert body["results"][0]["error"] == "boom"
