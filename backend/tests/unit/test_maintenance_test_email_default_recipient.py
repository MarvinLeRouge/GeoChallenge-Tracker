"""Closes the Codecov patch-coverage gap from renaming ADMIN_DEST_EMAIL to
ADMIN_TEST_EMAIL (backend/app/api/routes/maintenance.py): no existing test
called POST /maintenance/test-email without an explicit to_email, so the
`recipient = to_email or settings.admin_test_email` fallback branch was never
exercised.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import require_admin
from app.api.routes import maintenance as maintenance_module
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(
        id=ObjectId(),
        username="admin",
        email="admin@example.com",
        role="admin",
    )
    app.dependency_overrides[require_admin] = lambda: admin_user
    return app


def _make_coll(count: int):
    coll = AsyncMock()
    coll.count_documents = AsyncMock(return_value=count)
    return coll


class TestTestEmailDefaultRecipient:
    @pytest.mark.asyncio
    async def test_falls_back_to_admin_test_email_when_to_email_omitted(self):
        app = _make_app()
        settings = MagicMock()
        settings.admin_test_email = "configured-admin@example.com"

        counts = {"users": 1, "caches": 2, "challenges": 3}

        async def _get_collection(name):
            return _make_coll(counts[name])

        with (
            patch.object(maintenance_module, "get_settings", return_value=settings),
            patch.object(maintenance_module, "get_collection", side_effect=_get_collection),
            patch.object(
                maintenance_module, "send_test_email", new_callable=AsyncMock
            ) as mock_send,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/maintenance/test-email")

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Test email sent to configured-admin@example.com"
        assert body["stats"] == {"users": 1, "caches": 2, "challenges": 3}
        mock_send.assert_awaited_once_with(
            to_email="configured-admin@example.com",
            user_count=1,
            cache_count=2,
            challenge_count=3,
        )
