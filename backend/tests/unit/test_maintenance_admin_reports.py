"""Tests for the smaller read-only admin diagnostic routes in maintenance.py,
previously uncovered: DELETE /maintenance/expired-verifications, GET /maintenance/
caches-geo-anomalies, GET /maintenance/snapshot, and GET /maintenance/
referentials-duplicates.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


async def _agen(docs):
    for doc in docs:
        yield doc


class TestCleanupExpiredVerifications:
    @pytest.mark.asyncio
    async def test_unsets_verification_fields_on_expired_accounts(self):
        coll_users = AsyncMock()
        coll_users.update_many = AsyncMock(return_value=MagicMock(modified_count=3))

        async def _get_collection(name):
            assert name == "users"
            return coll_users

        with patch.object(maintenance_module, "get_collection", side_effect=_get_collection):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete("/maintenance/expired-verifications")

        assert response.status_code == 200
        assert response.json() == {"cleaned": 3}
        coll_users.update_many.assert_awaited_once()
        filter_arg = coll_users.update_many.call_args.args[0]
        assert filter_arg["is_verified"] is False


class TestCachesGeoAnomalies:
    @pytest.mark.asyncio
    async def test_reports_counts_and_al_prefix_hypothesis(self):
        sample_doc = {
            "GC": "GCXYZ",
            "title": "Sample cache",
            "lat": None,
            "lon": None,
            "location_more": None,
        }
        coll_caches = AsyncMock()
        coll_caches.count_documents = AsyncMock(side_effect=[10, 4, 2, 1, 3, 1, 2, 3, 1])
        find_result = MagicMock()
        find_result.limit = MagicMock(return_value=_agen([sample_doc]))
        coll_caches.find = MagicMock(return_value=find_result)

        async def _get_collection(name):
            assert name == "caches"
            return coll_caches

        with patch.object(maintenance_module, "get_collection", side_effect=_get_collection):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/caches-geo-anomalies")

        assert response.status_code == 200
        body = response.json()
        assert body["total_caches"] == 10
        assert body["null_country_id"] == 4
        assert body["sample"] == [sample_doc]
        assert "al_prefix_hypothesis" in body


class TestSnapshot:
    @pytest.mark.asyncio
    async def test_returns_global_and_user_scoped_counts(self):
        user_id = str(ObjectId())

        coll_caches = AsyncMock()
        coll_caches.count_documents = AsyncMock(return_value=100)
        coll_challenges = AsyncMock()
        coll_challenges.count_documents = AsyncMock(return_value=20)
        coll_found = AsyncMock()
        coll_found.count_documents = AsyncMock(return_value=5)
        coll_ucs = AsyncMock()
        coll_ucs.count_documents = AsyncMock(return_value=3)
        coll_ucs.aggregate = MagicMock(
            side_effect=lambda pipeline: _agen(
                [{"_id": "accepted", "count": 2}, {"_id": None, "count": 1}]
            )
        )

        collections = {
            "caches": coll_caches,
            "challenges": coll_challenges,
            "found_caches": coll_found,
            "user_challenges": coll_ucs,
        }

        async def _get_collection(name):
            return collections[name]

        with patch.object(maintenance_module, "get_collection", side_effect=_get_collection):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/snapshot", params={"user_id": user_id})

        assert response.status_code == 200
        body = response.json()
        assert body["global"] == {"caches": 100, "challenges": 20}
        assert body["user"]["found_caches"] == 5
        assert body["user"]["user_challenges"] == 3
        assert body["user"]["user_challenges_by_computed_status"] == {"accepted": 2, "null": 1}


class TestReferentialsDuplicates:
    @pytest.mark.asyncio
    async def test_detects_duplicate_countries_and_states(self):
        country_a = ObjectId()
        country_b = ObjectId()
        state_a = ObjectId()
        state_b = ObjectId()
        shared_country_id = ObjectId()

        mock_db = MagicMock()
        mock_db.countries.find = MagicMock(
            return_value=_agen(
                [
                    {"_id": country_a, "name": "France"},
                    {"_id": country_b, "name": "Fränce"},
                ]
            )
        )
        mock_db.states.find = MagicMock(
            return_value=_agen(
                [
                    {"_id": state_a, "name": "Savoie", "country_id": shared_country_id},
                    {"_id": state_b, "name": "SAVOIE", "country_id": shared_country_id},
                ]
            )
        )

        with patch.object(maintenance_module, "get_db", return_value=mock_db):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/referentials-duplicates")

        assert response.status_code == 200
        body = response.json()
        assert body["nb_duplicate_country_groups"] == 1
        assert len(body["duplicate_countries"][0]["entries"]) == 2
        assert body["nb_duplicate_state_groups"] == 1
        assert len(body["duplicate_states"][0]["entries"]) == 2
