"""Tests for POST /caches_elevation/caches/elevation/backfill, previously
entirely untested. Covers the dry-run branch, the empty-buffer stop
condition, the per-point failure branch (missing elevation), and the
admin-only guard.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import caches_elevation as elevation_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(elevation_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


class TestBackfillDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_counts_without_writing(self):
        docs = [{"_id": ObjectId(), "lat": 45.0, "lon": 5.0} for _ in range(2)]
        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=[docs, []])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with patch.object(elevation_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches_elevation/caches/elevation/backfill",
                    params={"dry_run": "true", "limit": 2, "page_size": 10},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["dry_run"] is True
        assert body["scanned"] == 2
        assert body["updated"] == 0
        coll.bulk_write.assert_not_called()


class TestBackfillEmptyBuffer:
    @pytest.mark.asyncio
    async def test_no_matching_caches_returns_zeroed_stats(self):
        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with patch.object(elevation_module, "get_collection", new=AsyncMock(return_value=coll)):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/caches_elevation/caches/elevation/backfill")

        assert response.status_code == 200
        body = response.json()
        assert body["scanned"] == 0
        assert body["batches"] == 0


class TestBackfillUpdates:
    @pytest.mark.asyncio
    async def test_mixed_results_update_only_resolved_caches(self):
        doc_ok = {"_id": ObjectId(), "lat": 45.0, "lon": 5.0}
        doc_missing_elev = {"_id": ObjectId(), "lat": 46.0, "lon": 6.0}
        docs = [doc_ok, doc_missing_elev]

        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=[docs, []])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)
        coll.bulk_write = AsyncMock()

        with (
            patch.object(elevation_module, "get_collection", new=AsyncMock(return_value=coll)),
            patch.object(
                elevation_module, "fetch_elevations", new=AsyncMock(return_value=[1250, None])
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches_elevation/caches/elevation/backfill",
                    params={"limit": 2, "page_size": 10},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["scanned"] == 2
        assert body["updated"] == 1
        assert body["failed"] == 1

        coll.bulk_write.assert_awaited_once()
        ops = coll.bulk_write.call_args.args[0]
        assert len(ops) == 1


class TestBackfillRequiresAdmin:
    @pytest.mark.asyncio
    async def test_non_admin_user_is_rejected(self):
        app = FastAPI()
        app.include_router(elevation_module.router)
        regular_user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
        app.dependency_overrides[get_current_user] = lambda: regular_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/caches_elevation/caches/elevation/backfill")

        assert response.status_code == 403
