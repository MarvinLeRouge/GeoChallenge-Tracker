"""Tests for app/services/gpx_import/cache_persister.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.errors import BulkWriteError

from app.services.gpx_import.cache_persister import CachePersister

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    class MockDB:
        def __init__(self):
            self.caches = AsyncMock()
            self.found_caches = AsyncMock()
            self.countries = AsyncMock()
            self.states = AsyncMock()
            self.cache_types = AsyncMock()
            self.cache_sizes = AsyncMock()

    return MockDB()


def _make_persister(db=None):
    return CachePersister(db or _make_db())


# ---------------------------------------------------------------------------
# persist_caches
# ---------------------------------------------------------------------------


class TestPersistCaches:
    @pytest.mark.asyncio
    async def test_returns_zeros_when_empty(self):
        persister = _make_persister()
        result = await persister.persist_caches([])
        assert result == {"inserted": 0, "updated": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_bulk_write_success(self):
        db = _make_db()
        bw_result = MagicMock()
        bw_result.upserted_count = 2
        bw_result.modified_count = 1
        db.caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        result = await persister.persist_caches([{"GC": "GC1"}, {"GC": "GC2"}])

        assert result["inserted"] == 2
        assert result["updated"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_force_update_attributes(self):
        db = _make_db()
        bw_result = MagicMock()
        bw_result.upserted_count = 1
        bw_result.modified_count = 0
        db.caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        await persister.persist_caches(
            [{"GC": "GC1", "attributes": ["terrain:3"]}],
            force_update_attributes=True,
        )

        call_args = db.caches.bulk_write.call_args[0][0]
        # The $set must contain attributes
        assert "attributes" in call_args[0]._doc["$set"]

    @pytest.mark.asyncio
    async def test_bulk_write_error_partial_results(self):
        db = _make_db()
        error = BulkWriteError(
            {
                "nUpserted": 1,
                "nModified": 2,
                "writeErrors": [{"index": 0, "code": 11000}],
            }
        )
        db.caches.bulk_write = AsyncMock(side_effect=error)

        persister = _make_persister(db)
        result = await persister.persist_caches([{"GC": "GC1"}])

        assert result["inserted"] == 1
        assert result["updated"] == 2
        assert result["errors"] == 1


# ---------------------------------------------------------------------------
# persist_found_caches
# ---------------------------------------------------------------------------


class TestPersistFoundCaches:
    @pytest.mark.asyncio
    async def test_returns_zeros_when_empty(self):
        persister = _make_persister()
        result = await persister.persist_found_caches([], ObjectId())
        assert result == {"inserted": 0, "updated": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_skips_caches_not_found_in_db(self):
        db = _make_db()
        db.caches.find_one = AsyncMock(return_value=None)

        bw_result = MagicMock()
        bw_result.upserted_count = 0
        bw_result.modified_count = 0
        db.found_caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        result = await persister.persist_found_caches(
            [{"GC": "GC_UNKNOWN", "found_date": "2024-01-01"}],
            ObjectId(),
        )

        assert result == {"inserted": 0, "updated": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_bulk_write_success(self):
        db = _make_db()
        cache_id = ObjectId()
        db.caches.find_one = AsyncMock(return_value={"_id": cache_id})

        bw_result = MagicMock()
        bw_result.upserted_count = 1
        bw_result.modified_count = 0
        db.found_caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        result = await persister.persist_found_caches(
            [{"GC": "GC1", "found_date": "2024-01-01"}],
            ObjectId(),
        )

        assert result["inserted"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_notes_none_adds_unset(self):
        db = _make_db()
        cache_id = ObjectId()
        db.caches.find_one = AsyncMock(return_value={"_id": cache_id})

        bw_result = MagicMock()
        bw_result.upserted_count = 0
        bw_result.modified_count = 1
        db.found_caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        await persister.persist_found_caches(
            [{"GC": "GC1", "found_date": "2024-01-01", "notes": None}],
            ObjectId(),
        )

        ops = db.found_caches.bulk_write.call_args[0][0]
        assert "$unset" in ops[0]._doc

    @pytest.mark.asyncio
    async def test_notes_string_adds_to_set(self):
        db = _make_db()
        cache_id = ObjectId()
        db.caches.find_one = AsyncMock(return_value={"_id": cache_id})

        bw_result = MagicMock()
        bw_result.upserted_count = 0
        bw_result.modified_count = 1
        db.found_caches.bulk_write = AsyncMock(return_value=bw_result)

        persister = _make_persister(db)
        await persister.persist_found_caches(
            [{"GC": "GC1", "found_date": "2024-01-01", "notes": "Great cache!"}],
            ObjectId(),
        )

        ops = db.found_caches.bulk_write.call_args[0][0]
        assert ops[0]._doc["$set"]["notes"] == "Great cache!"

    @pytest.mark.asyncio
    async def test_bulk_write_error_partial_results(self):
        db = _make_db()
        cache_id = ObjectId()
        db.caches.find_one = AsyncMock(return_value={"_id": cache_id})

        error = BulkWriteError(
            {
                "nUpserted": 0,
                "nModified": 0,
                "writeErrors": [{"index": 0, "code": 11000}],
            }
        )
        db.found_caches.bulk_write = AsyncMock(side_effect=error)

        persister = _make_persister(db)
        result = await persister.persist_found_caches(
            [{"GC": "GC1", "found_date": "2024-01-01"}],
            ObjectId(),
        )

        assert result["errors"] == 1


# ---------------------------------------------------------------------------
# _get_cache_id_by_gc
# ---------------------------------------------------------------------------


class TestGetCacheIdByGc:
    @pytest.mark.asyncio
    async def test_returns_id_when_found(self):
        db = _make_db()
        oid = ObjectId()
        db.caches.find_one = AsyncMock(return_value={"_id": oid})

        persister = _make_persister(db)
        result = await persister._get_cache_id_by_gc("GC1")
        assert result == oid

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.caches.find_one = AsyncMock(return_value=None)

        persister = _make_persister(db)
        result = await persister._get_cache_id_by_gc("GC_MISSING")
        assert result is None


# ---------------------------------------------------------------------------
# get_existing_caches_by_gc
# ---------------------------------------------------------------------------


class TestGetExistingCachesByGc:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_input(self):
        persister = _make_persister()
        result = await persister.get_existing_caches_by_gc([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_gc_to_id_mapping(self):
        db = _make_db()
        id1, id2 = ObjectId(), ObjectId()

        async def aiter_docs():
            for doc in [{"GC": "GC1", "_id": id1}, {"GC": "GC2", "_id": id2}]:
                yield doc

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=aiter_docs())
        db.caches.find = MagicMock(return_value=mock_cursor)

        persister = _make_persister(db)
        result = await persister.get_existing_caches_by_gc(["GC1", "GC2"])

        assert result == {"GC1": id1, "GC2": id2}


# ---------------------------------------------------------------------------
# count_existing_found_caches
# ---------------------------------------------------------------------------


class TestCountExistingFoundCaches:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_gc_codes(self):
        persister = _make_persister()
        result = await persister.count_existing_found_caches(ObjectId(), [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_caches_found(self):
        db = _make_db()

        async def aiter_empty():
            return
            yield  # pragma: no cover

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=aiter_empty())
        db.caches.find = MagicMock(return_value=mock_cursor)

        persister = _make_persister(db)
        result = await persister.count_existing_found_caches(ObjectId(), ["GC_MISSING"])
        assert result == 0

    @pytest.mark.asyncio
    async def test_delegates_count_to_found_caches(self):
        db = _make_db()
        cache_id = ObjectId()

        async def aiter_docs():
            yield {"GC": "GC1", "_id": cache_id}

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=aiter_docs())
        db.caches.find = MagicMock(return_value=mock_cursor)
        db.found_caches.count_documents = AsyncMock(return_value=3)

        persister = _make_persister(db)
        result = await persister.count_existing_found_caches(ObjectId(), ["GC1"])
        assert result == 3


# ---------------------------------------------------------------------------
# get_referential_counts
# ---------------------------------------------------------------------------


class TestGetReferentialCounts:
    @pytest.mark.asyncio
    async def test_returns_counts_for_all_collections(self):
        db = _make_db()
        db.countries.count_documents = AsyncMock(return_value=50)
        db.states.count_documents = AsyncMock(return_value=200)
        db.cache_types.count_documents = AsyncMock(return_value=10)
        db.cache_sizes.count_documents = AsyncMock(return_value=5)

        persister = _make_persister(db)
        result = await persister.get_referential_counts()

        assert result == {
            "countries": 50,
            "states": 200,
            "cache_types": 10,
            "cache_sizes": 5,
        }


# ---------------------------------------------------------------------------
# cleanup_temp_data
# ---------------------------------------------------------------------------


class TestCleanupTempData:
    @pytest.mark.asyncio
    async def test_runs_without_error(self):
        persister = _make_persister()
        await persister.cleanup_temp_data(["GC1", "GC2"])
