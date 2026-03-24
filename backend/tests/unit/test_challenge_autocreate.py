"""Tests for challenge_autocreate service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.challenge_autocreate import (
    _get_attribute_doc_id,
    _iter_new_challenge_caches_all,
    _iter_new_challenge_caches_subset,
    create_challenges_from_caches,
    create_new_challenges_from_caches,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncIter:
    """Async-iterable wrapper around a regular list."""

    def __init__(self, items):
        self._iter = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as err:
            raise StopAsyncIteration from err


def _make_coll():
    coll = AsyncMock()
    coll.distinct = AsyncMock(return_value=[])
    return coll


def _patch_gc(**mapping):
    """Patch get_collection to dispatch by name."""
    defaults = {
        "cache_attributes": _make_coll(),
        "caches": _make_coll(),
        "challenges": _make_coll(),
    }
    defaults.update(mapping)

    async def _get(name):
        return defaults.get(name, _make_coll())

    return patch("app.services.challenge_autocreate.get_collection", side_effect=_get)


# ---------------------------------------------------------------------------
# _get_attribute_doc_id
# ---------------------------------------------------------------------------


class TestGetAttributeDocId:
    @pytest.mark.asyncio
    async def test_returns_doc_id_when_found(self):
        attr_id = ObjectId()
        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        with _patch_gc(cache_attributes=attrs_coll):
            result = await _get_attribute_doc_id()

        assert result == attr_id

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_not_found(self):
        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value=None)

        with _patch_gc(cache_attributes=attrs_coll):
            with pytest.raises(RuntimeError, match="cache_attribute_id=71"):
                await _get_attribute_doc_id()

    @pytest.mark.asyncio
    async def test_accepts_custom_attribute_id(self):
        attr_id = ObjectId()
        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        with _patch_gc(cache_attributes=attrs_coll):
            result = await _get_attribute_doc_id(attribute_id=99)

        assert result == attr_id
        call_filter = attrs_coll.find_one.call_args[0][0]
        assert call_filter["cache_attribute_id"] == 99


# ---------------------------------------------------------------------------
# _iter_new_challenge_caches_all
# ---------------------------------------------------------------------------


class TestIterNewChallengeCachesAll:
    @pytest.mark.asyncio
    async def test_returns_aggregate_cursor(self):
        cursor = _AsyncIter([])
        caches_coll = _make_coll()
        caches_coll.aggregate = MagicMock(return_value=cursor)

        with _patch_gc(caches=caches_coll):
            result = await _iter_new_challenge_caches_all(ObjectId())

        assert result is cursor
        caches_coll.aggregate.assert_called_once()


# ---------------------------------------------------------------------------
# _iter_new_challenge_caches_subset
# ---------------------------------------------------------------------------


class TestIterNewChallengeCachesSubset:
    @pytest.mark.asyncio
    async def test_returns_empty_iter_when_no_cache_ids(self):
        with _patch_gc():
            result = await _iter_new_challenge_caches_subset(ObjectId(), [])

        items = list(result)
        assert items == []

    @pytest.mark.asyncio
    async def test_returns_find_cursor_with_cache_ids(self):
        cache_id = ObjectId()
        cursor = MagicMock()

        caches_coll = _make_coll()
        caches_coll.find = MagicMock(return_value=cursor)

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[])  # no known IDs

        with _patch_gc(caches=caches_coll, challenges=challenges_coll):
            result = await _iter_new_challenge_caches_subset(ObjectId(), [cache_id])

        assert result is cursor

    @pytest.mark.asyncio
    async def test_excludes_already_known_ids(self):
        cache_id1 = ObjectId()
        cache_id2 = ObjectId()

        caches_coll = _make_coll()
        caches_coll.find = MagicMock(return_value=MagicMock())

        challenges_coll = _make_coll()
        # cache_id1 already known
        challenges_coll.distinct = AsyncMock(return_value=[cache_id1])

        with _patch_gc(caches=caches_coll, challenges=challenges_coll):
            await _iter_new_challenge_caches_subset(ObjectId(), [cache_id1, cache_id2])

        call_filter = caches_coll.find.call_args[0][0]
        assert cache_id1 not in call_filter["_id"]["$in"]
        assert cache_id2 in call_filter["_id"]["$in"]


# ---------------------------------------------------------------------------
# create_challenges_from_caches
# ---------------------------------------------------------------------------


class TestCreateChallengesFromCaches:
    @pytest.mark.asyncio
    async def test_no_cache_ids_scans_all_returns_empty(self):
        attr_id = ObjectId()
        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.aggregate = MagicMock(return_value=_AsyncIter([]))

        challenges_coll = _make_coll()

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_challenges_from_caches()

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_with_cache_ids_uses_subset_path(self):
        attr_id = ObjectId()
        cache_id = ObjectId()

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.find = MagicMock(return_value=_AsyncIter([]))

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[])

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_challenges_from_caches(cache_ids=[cache_id])

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_creates_challenges_from_matching_caches(self):
        attr_id = ObjectId()
        cache_id = ObjectId()
        cache_doc = {"_id": cache_id, "title": "My Challenge", "description_html": "<p>desc</p>"}

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.find = MagicMock(return_value=_AsyncIter([cache_doc]))

        bulk_result = MagicMock()
        bulk_result.upserted_ids = {0: ObjectId()}

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[])
        challenges_coll.bulk_write = AsyncMock(return_value=bulk_result)

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_challenges_from_caches(cache_ids=[cache_id])

        assert result["matched"] == 1
        assert result["created"] == 1
        assert result["skipped_existing"] == 0

    @pytest.mark.asyncio
    async def test_uses_default_title_when_cache_has_none(self):
        """Cache doc without title → "Challenge" default."""
        attr_id = ObjectId()
        cache_id = ObjectId()
        cache_doc = {"_id": cache_id}  # no title, no description_html

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.find = MagicMock(return_value=_AsyncIter([cache_doc]))

        bulk_result = MagicMock()
        bulk_result.upserted_ids = {}

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[])
        challenges_coll.bulk_write = AsyncMock(return_value=bulk_result)

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_challenges_from_caches(cache_ids=[cache_id])

        assert result["matched"] == 1
        op = challenges_coll.bulk_write.call_args[0][0][0]
        assert op._doc["$set"]["name"] == "Challenge"


# ---------------------------------------------------------------------------
# create_new_challenges_from_caches
# ---------------------------------------------------------------------------


class TestCreateNewChallengesFromCaches:
    @pytest.mark.asyncio
    async def test_empty_cache_ids_returns_zeros(self):
        attr_id = ObjectId()
        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        with _patch_gc(cache_attributes=attrs_coll):
            result = await create_new_challenges_from_caches(cache_ids=[])

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_all_known_ids_returns_zeros(self):
        attr_id = ObjectId()
        cache_id = ObjectId()

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[cache_id])  # already known

        with _patch_gc(cache_attributes=attrs_coll, challenges=challenges_coll):
            result = await create_new_challenges_from_caches(cache_ids=[cache_id])

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_no_candidate_caches_returns_zeros(self):
        """No cache_ids, but caches.distinct returns empty → no work done."""
        attr_id = ObjectId()

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.distinct = AsyncMock(return_value=[])  # no challenge caches

        challenges_coll = _make_coll()

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_new_challenges_from_caches()

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_all_candidate_ids_already_known_returns_zeros(self):
        """All candidates already in challenges → skipped without calling create."""
        attr_id = ObjectId()
        cache_id = ObjectId()

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.distinct = AsyncMock(return_value=[cache_id])

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[cache_id])  # already known

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_new_challenges_from_caches()

        assert result == {"matched": 0, "created": 0, "skipped_existing": 0}

    @pytest.mark.asyncio
    async def test_delegates_to_create_with_new_ids(self):
        """New IDs that pass filtering → delegates to create_challenges_from_caches."""
        attr_id = ObjectId()
        cache_id = ObjectId()

        attrs_coll = _make_coll()
        attrs_coll.find_one = AsyncMock(return_value={"_id": attr_id})

        caches_coll = _make_coll()
        caches_coll.distinct = AsyncMock(return_value=[cache_id])

        challenges_coll = _make_coll()
        challenges_coll.distinct = AsyncMock(return_value=[])  # none known yet
        challenges_coll.bulk_write = AsyncMock(return_value=MagicMock(upserted_ids={}))
        # aggregate returns empty so matched=0
        caches_coll.aggregate = MagicMock(return_value=_AsyncIter([]))
        caches_coll.find = MagicMock(return_value=_AsyncIter([]))

        with _patch_gc(
            cache_attributes=attrs_coll,
            caches=caches_coll,
            challenges=challenges_coll,
        ):
            result = await create_new_challenges_from_caches()

        assert "matched" in result
