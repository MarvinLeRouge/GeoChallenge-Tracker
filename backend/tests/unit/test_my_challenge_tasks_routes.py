"""Tests for GET/PUT /my/challenges/{uc_id}/tasks and POST /my/challenges/
{uc_id}/tasks/validate - none of which had any prior coverage. Covers the
happy paths and the ValueError -> 422 branch of put_tasks_route.
"""

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import my_challenge_tasks as tasks_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(tasks_module.router)

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class TestGetTasks:
    @pytest.mark.asyncio
    async def test_returns_ordered_tasks(self):
        uc_id = ObjectId()
        with patch.object(tasks_module, "list_tasks", new=AsyncMock(return_value=[])):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/my/challenges/{uc_id}/tasks")

        assert response.status_code == 200
        assert response.json() == {"tasks": []}


class TestPutTasksRoute:
    @pytest.mark.asyncio
    async def test_success_replaces_tasks(self):
        uc_id = ObjectId()
        with patch.object(tasks_module, "put_tasks", new=AsyncMock(return_value=[])) as mock_put:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(f"/my/challenges/{uc_id}/tasks", json={"tasks": []})

        assert response.status_code == 200
        assert response.json() == {"tasks": []}
        mock_put.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_tasks_returns_422(self):
        uc_id = ObjectId()
        with patch.object(
            tasks_module,
            "put_tasks",
            new=AsyncMock(side_effect=ValueError("duplicate task order")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(f"/my/challenges/{uc_id}/tasks", json={"tasks": []})

        assert response.status_code == 422
        assert response.json()["detail"] == "duplicate task order"


class TestValidateTasksRoute:
    @pytest.mark.asyncio
    async def test_returns_validation_result(self):
        uc_id = ObjectId()
        with patch.object(
            tasks_module, "validate_only", return_value={"ok": True, "errors": []}
        ) as mock_validate:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/my/challenges/{uc_id}/tasks/validate", json={"tasks": []}
                )

        assert response.status_code == 200
        assert response.json() == {"ok": True, "errors": []}
        mock_validate.assert_called_once()
