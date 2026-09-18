"""Tests for GET/DELETE /maintenance/db_cleanup (orphan detection and cleanup).

Closes the Codecov coverage gap on cleanup_analyze/cleanup_execute, the two
largest untested functions in maintenance.py. get_collection is mocked per
collection name: only the collections relevant to a given scenario carry
data, everything else in the dependency graph resolves to an empty collection
(no orphans).

clean_expired_keys() is called with no argument in both routes, so it binds
to PENDING_CLEANUP_DIR's value at module-import time rather than any value
patched later via patch.object - unlike PENDING_RESTORE_DIR in
db_full_restore, which is passed explicitly. To keep these tests hermetic
(not dependent on the real backups/pending_cleanups directory being absent),
clean_expired_keys itself is patched to a no-op.
"""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.core.utils import utcnow
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


def _empty_collection():
    coll = AsyncMock()
    coll.distinct = AsyncMock(return_value=[])
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    coll.aggregate = MagicMock(return_value=cursor)
    coll.find = MagicMock(return_value=cursor)
    coll.delete_many = AsyncMock(return_value=MagicMock(deleted_count=0))
    return coll


def _collection_registry(overrides: dict):
    async def _get_collection(name):
        return overrides.get(name, _empty_collection())

    return _get_collection


class TestCleanupAnalyze:
    @pytest.mark.asyncio
    async def test_no_orphans_returns_clean_message_without_key(self):
        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(
                maintenance_module, "get_collection", side_effect=_collection_registry({})
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/db_cleanup")

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "No orphans found. Database is clean!"
        assert body["total_orphans"] == 0
        assert "confirmation_key" not in body

    @pytest.mark.asyncio
    async def test_simple_orphan_reference_returns_confirmation_key(self, tmp_path):
        country_id = ObjectId()
        orphan_state_id = ObjectId()

        countries_coll = _empty_collection()
        countries_coll.distinct = AsyncMock(return_value=[country_id])

        states_coll = _empty_collection()
        orphan_cursor = MagicMock()
        orphan_cursor.to_list = AsyncMock(return_value=[{"_id": orphan_state_id}])
        states_coll.aggregate = MagicMock(return_value=orphan_cursor)

        pending_dir = tmp_path / "pending_cleanups"

        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(maintenance_module, "PENDING_CLEANUP_DIR", pending_dir),
            patch.object(
                maintenance_module,
                "get_collection",
                side_effect=_collection_registry(
                    {"countries": countries_coll, "states": states_coll}
                ),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/db_cleanup")

        assert response.status_code == 200
        body = response.json()
        assert body["total_orphans"] == 1
        assert body["orphans_found"]["states.country_id"] == [str(orphan_state_id)]
        assert "confirmation_key" in body
        assert (pending_dir / f"{body['confirmation_key']}.json").exists()

    @pytest.mark.asyncio
    async def test_nested_attribute_orphan_is_detected(self, tmp_path):
        """caches.attributes.attribute_doc_id -> cache_attributes is the one nested-array
        reference in REFERENCES_MAP, handled by a dedicated $unwind/$lookup pipeline
        instead of the regular $nin pipeline used for flat references."""
        orphan_cache_id = ObjectId()

        caches_coll = _empty_collection()
        nested_cursor = MagicMock()
        nested_cursor.to_list = AsyncMock(
            return_value=[{"_id": None, "orphan_ids": [orphan_cache_id]}]
        )
        regular_cursor = MagicMock()
        regular_cursor.to_list = AsyncMock(return_value=[])

        def _caches_aggregate(pipeline, *args, **kwargs):
            # caches is also queried with the regular (flat) orphan pipeline for its
            # own country_id/state_id/type_id/size_id references - only the nested
            # $unwind on "attributes" should return the simulated orphan.
            if any(stage.get("$unwind") == "$attributes" for stage in pipeline):
                return nested_cursor
            return regular_cursor

        caches_coll.aggregate = MagicMock(side_effect=_caches_aggregate)

        pending_dir = tmp_path / "pending_cleanups"

        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(maintenance_module, "PENDING_CLEANUP_DIR", pending_dir),
            patch.object(
                maintenance_module,
                "get_collection",
                side_effect=_collection_registry({"caches": caches_coll}),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/db_cleanup")

        assert response.status_code == 200
        body = response.json()
        assert body["orphans_found"]["caches.attributes.attribute_doc_id"] == [str(orphan_cache_id)]


class TestCleanupExecute:
    @pytest.mark.asyncio
    async def test_invalid_key_raises_404(self, tmp_path):
        pending_dir = tmp_path / "pending_cleanups"

        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(maintenance_module, "PENDING_CLEANUP_DIR", pending_dir),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete(
                    "/maintenance/db_cleanup", params={"key": "not-a-real-key"}
                )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_key_raises_410(self, tmp_path):
        pending_dir = tmp_path / "pending_cleanups"
        pending_dir.mkdir(parents=True)
        expired_key = "expired-key"
        (pending_dir / f"{expired_key}.json").write_text(
            json.dumps(
                {
                    "orphans": {"states.country_id": [str(ObjectId())]},
                    "expires_at": (utcnow() - timedelta(minutes=1)).isoformat(),
                }
            )
        )

        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(maintenance_module, "PENDING_CLEANUP_DIR", pending_dir),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete(
                    "/maintenance/db_cleanup", params={"key": expired_key}
                )

        assert response.status_code == 410
        assert not (pending_dir / f"{expired_key}.json").exists()

    @pytest.mark.asyncio
    async def test_valid_key_deletes_orphans_and_writes_backup(self, tmp_path):
        orphan_state_id = ObjectId()
        pending_dir = tmp_path / "pending_cleanups"
        pending_dir.mkdir(parents=True)
        key = "valid-key"
        (pending_dir / f"{key}.json").write_text(
            json.dumps(
                {
                    "orphans": {"states.country_id": [str(orphan_state_id)]},
                    "expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
                }
            )
        )

        states_coll = _empty_collection()
        found_cursor = MagicMock()
        found_cursor.to_list = AsyncMock(
            return_value=[{"_id": orphan_state_id, "name": "Orphan State"}]
        )
        states_coll.find = MagicMock(return_value=found_cursor)
        states_coll.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))

        backup_dir = tmp_path / "db_cleanup_backups"

        with (
            patch.object(maintenance_module, "clean_expired_keys"),
            patch.object(maintenance_module, "PENDING_CLEANUP_DIR", pending_dir),
            patch.object(maintenance_module, "CLEANUP_BACKUP_DIR", backup_dir),
            patch.object(
                maintenance_module,
                "get_collection",
                side_effect=_collection_registry({"states": states_coll}),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.delete("/maintenance/db_cleanup", params={"key": key})

        assert response.status_code == 200
        body = response.json()
        assert body["deleted"] == {"states": 1}
        assert body["total_deleted"] == 1
        assert body["message"] == "Successfully deleted 1 orphan(s)"
        states_coll.delete_many.assert_awaited_once_with({"_id": {"$in": [orphan_state_id]}})
        # The key must be single-use.
        assert not (pending_dir / f"{key}.json").exists()
        # A real backup zip was written under the (patched) backup directory.
        backup_file = tmp_path / "db_cleanup_backups" / f"{body['backup_file'].split('/')[-1]}"
        assert backup_file.exists()
