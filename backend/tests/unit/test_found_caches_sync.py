# tests/unit/test_found_caches_sync.py
# Unit tests for the found_caches_sync service.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.found_caches_sync import extract_gc_codes, sync_found_caches

# ---------------------------------------------------------------------------
# extract_gc_codes
# ---------------------------------------------------------------------------


class TestExtractGcCodes:
    def test_extracts_single_code(self):
        assert extract_gc_codes("Found GC1234A today") == ["GC1234A"]

    def test_extracts_multiple_codes(self):
        result = extract_gc_codes("GC1234 and GC5678 were great finds")
        assert result == ["GC1234", "GC5678"]

    def test_deduplicates_codes(self):
        result = extract_gc_codes("GC1234 GC1234 gc1234")
        assert result == ["GC1234"]

    def test_normalises_to_uppercase(self):
        assert extract_gc_codes("gc1234a") == ["GC1234A"]

    def test_ignores_non_gc_patterns(self):
        assert extract_gc_codes("no codes here, just text") == []

    def test_does_not_match_partial_prefix(self):
        # "XGC1234" should not match because of the word boundary
        assert extract_gc_codes("XGC1234") == []

    def test_preserves_first_seen_order(self):
        result = extract_gc_codes("GC000B GC000A GC000C GC000A")
        assert result == ["GC000B", "GC000A", "GC000C"]

    def test_empty_string_returns_empty(self):
        assert extract_gc_codes("") == []

    def test_multiline_text(self):
        text = "GC0001\nGC0002\nGC0003"
        assert extract_gc_codes(text) == ["GC0001", "GC0002", "GC0003"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    db = MagicMock()
    db.caches = MagicMock()
    db.found_caches = MagicMock()
    return db


# ---------------------------------------------------------------------------
# sync_found_caches
# ---------------------------------------------------------------------------


class TestSyncFoundCaches:
    @pytest.mark.asyncio
    async def test_adds_new_found_caches(self):
        db = _make_db()
        user_id = ObjectId()
        cache_id = ObjectId()

        # One known cache
        known_cursor = AsyncMock()
        known_cursor.to_list = AsyncMock(return_value=[{"_id": cache_id, "GC": "GC0001"}])
        db.caches.find = MagicMock(return_value=known_cursor)

        # No existing found caches
        existing_cursor = AsyncMock()
        existing_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.find = MagicMock(return_value=existing_cursor)

        ins_result = MagicMock()
        ins_result.inserted_ids = [ObjectId()]
        db.found_caches.insert_many = AsyncMock(return_value=ins_result)

        result = await sync_found_caches(db, user_id, ["GC0001"])

        assert result["nb_provided"] == 1
        assert result["nb_added"] == 1
        assert result["nb_deleted"] == 0
        assert result["nb_unknown_gc"] == 0
        assert result["unknown_gc_codes"] == []
        db.found_caches.insert_many.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deletes_removed_found_caches(self):
        db = _make_db()
        user_id = ObjectId()
        cache_id = ObjectId()

        # No known caches in the input list
        known_cursor = AsyncMock()
        known_cursor.to_list = AsyncMock(return_value=[])
        db.caches.find = MagicMock(return_value=known_cursor)

        # One existing found cache to remove
        existing_cursor = AsyncMock()
        existing_cursor.to_list = AsyncMock(
            return_value=[{"_id": ObjectId(), "cache_id": cache_id}]
        )
        db.found_caches.find = MagicMock(return_value=existing_cursor)

        del_result = MagicMock()
        del_result.deleted_count = 1
        db.found_caches.delete_many = AsyncMock(return_value=del_result)

        result = await sync_found_caches(db, user_id, [])

        assert result["nb_deleted"] == 1
        assert result["nb_added"] == 0
        db.found_caches.delete_many.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reports_unknown_gc_codes(self):
        db = _make_db()
        user_id = ObjectId()

        # No matching cache in DB
        known_cursor = AsyncMock()
        known_cursor.to_list = AsyncMock(return_value=[])
        db.caches.find = MagicMock(return_value=known_cursor)

        existing_cursor = AsyncMock()
        existing_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.find = MagicMock(return_value=existing_cursor)

        result = await sync_found_caches(db, user_id, ["GCUNKNOWN"])

        assert result["nb_provided"] == 1
        assert result["nb_unknown_gc"] == 1
        assert result["unknown_gc_codes"] == ["GCUNKNOWN"]
        assert result["nb_added"] == 0
        assert result["nb_deleted"] == 0

    @pytest.mark.asyncio
    async def test_no_change_when_already_in_sync(self):
        db = _make_db()
        user_id = ObjectId()
        cache_id = ObjectId()

        known_cursor = AsyncMock()
        known_cursor.to_list = AsyncMock(return_value=[{"_id": cache_id, "GC": "GC0001"}])
        db.caches.find = MagicMock(return_value=known_cursor)

        existing_cursor = AsyncMock()
        existing_cursor.to_list = AsyncMock(
            return_value=[{"_id": ObjectId(), "cache_id": cache_id}]
        )
        db.found_caches.find = MagicMock(return_value=existing_cursor)

        result = await sync_found_caches(db, user_id, ["GC0001"])

        assert result["nb_added"] == 0
        assert result["nb_deleted"] == 0
        db.found_caches.insert_many.assert_not_called()
        db.found_caches.delete_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_input_clears_all_found_caches(self):
        db = _make_db()
        user_id = ObjectId()
        cache_id = ObjectId()

        known_cursor = AsyncMock()
        known_cursor.to_list = AsyncMock(return_value=[])
        db.caches.find = MagicMock(return_value=known_cursor)

        existing_cursor = AsyncMock()
        existing_cursor.to_list = AsyncMock(
            return_value=[{"_id": ObjectId(), "cache_id": cache_id}]
        )
        db.found_caches.find = MagicMock(return_value=existing_cursor)

        del_result = MagicMock()
        del_result.deleted_count = 1
        db.found_caches.delete_many = AsyncMock(return_value=del_result)

        result = await sync_found_caches(db, user_id, [])

        assert result["nb_deleted"] == 1
        assert result["nb_added"] == 0
