"""Tests for POST /caches_geocoding/backfill, previously entirely untested.
Covers the dry-run branch, the empty-buffer stop condition, the per-point
failure branches (geocoding miss, unresolved country), the state_id-present-
vs-absent update shape, and the had_non_200 flag.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import caches_geocoding as geocoding_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(geocoding_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


def _mock_mapper():
    mapper = AsyncMock()
    mapper.load_all_referentials = AsyncMock(return_value=None)
    return mapper


class TestBackfillDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_counts_without_writing(self):
        docs = [{"_id": ObjectId(), "lat": 45.0, "lon": 5.0} for _ in range(3)]
        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=[docs, []])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with (
            patch.object(geocoding_module, "get_collection", new=AsyncMock(return_value=coll)),
            patch.object(geocoding_module, "get_db", return_value=MagicMock()),
            patch.object(geocoding_module, "ReferentialMapper", return_value=_mock_mapper()),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches_geocoding/backfill",
                    params={"dry_run": "true", "limit": 3, "page_size": 3},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["dry_run"] is True
        assert body["scanned"] == 3
        assert body["updated"] == 0
        coll.bulk_write.assert_not_called()


class TestBackfillEmptyBuffer:
    @pytest.mark.asyncio
    async def test_no_matching_caches_returns_zeroed_stats(self):
        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with (
            patch.object(geocoding_module, "get_collection", new=AsyncMock(return_value=coll)),
            patch.object(geocoding_module, "get_db", return_value=MagicMock()),
            patch.object(geocoding_module, "ReferentialMapper", return_value=_mock_mapper()),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/caches_geocoding/backfill")

        assert response.status_code == 200
        body = response.json()
        assert body["scanned"] == 0
        assert body["batches"] == 0


class TestBackfillGeocodingAndUpdates:
    @pytest.mark.asyncio
    async def test_mixed_results_update_only_resolved_caches(self):
        doc_ok_with_state = {"_id": ObjectId(), "lat": 45.0, "lon": 5.0}
        doc_ok_no_state = {"_id": ObjectId(), "lat": 46.0, "lon": 6.0}
        doc_geocode_miss = {"_id": ObjectId(), "lat": 47.0, "lon": 7.0}
        doc_country_unresolved = {"_id": ObjectId(), "lat": 48.0, "lon": 8.0}
        docs = [doc_ok_with_state, doc_ok_no_state, doc_geocode_miss, doc_country_unresolved]

        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=[docs, []])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)
        coll.bulk_write = AsyncMock()

        country_id = ObjectId()
        state_id = ObjectId()

        mapper = _mock_mapper()
        mapper.ensure_country_and_state = AsyncMock(
            side_effect=[
                (country_id, state_id),
                (country_id, None),
                (None, None),  # unresolved country
            ]
        )

        geo_results = [
            ("France", "Savoie"),
            ("France", None),
            None,  # geocoding miss, no ensure_country_and_state call for this one
            ("Unknownland", None),
        ]

        with (
            patch.object(geocoding_module, "get_collection", new=AsyncMock(return_value=coll)),
            patch.object(geocoding_module, "get_db", return_value=MagicMock()),
            patch.object(geocoding_module, "ReferentialMapper", return_value=mapper),
            patch.object(
                geocoding_module.geocoding_nominatim,
                "fetch_batch",
                new=AsyncMock(return_value=(geo_results, {200: 3, 404: 1})),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches_geocoding/backfill", params={"limit": 4, "page_size": 4}
                )

        assert response.status_code == 200
        body = response.json()
        assert body["scanned"] == 4
        assert body["updated"] == 2
        assert body["failed"] == 2
        assert body["had_non_200"] is True

        coll.bulk_write.assert_awaited_once()
        ops = coll.bulk_write.call_args.args[0]
        assert len(ops) == 2

    @pytest.mark.asyncio
    async def test_all_http_200_reports_had_non_200_false(self):
        doc = {"_id": ObjectId(), "lat": 45.0, "lon": 5.0}
        cursor = MagicMock()
        cursor.limit = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=[[doc], []])))
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)
        coll.bulk_write = AsyncMock()

        mapper = _mock_mapper()
        mapper.ensure_country_and_state = AsyncMock(return_value=(ObjectId(), None))

        with (
            patch.object(geocoding_module, "get_collection", new=AsyncMock(return_value=coll)),
            patch.object(geocoding_module, "get_db", return_value=MagicMock()),
            patch.object(geocoding_module, "ReferentialMapper", return_value=mapper),
            patch.object(
                geocoding_module.geocoding_nominatim,
                "fetch_batch",
                new=AsyncMock(return_value=([("France", None)], {200: 1})),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches_geocoding/backfill", params={"limit": 1, "page_size": 1}
                )

        assert response.status_code == 200
        assert response.json()["had_non_200"] is False


class TestBackfillRequiresAdmin:
    @pytest.mark.asyncio
    async def test_non_admin_user_is_rejected(self):
        app = FastAPI()
        app.include_router(geocoding_module.router)
        regular_user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
        app.dependency_overrides[get_current_user] = lambda: regular_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/caches_geocoding/backfill")

        assert response.status_code == 403
