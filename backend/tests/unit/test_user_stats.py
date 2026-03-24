"""Tests for user_stats service functions."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.user_stats import get_user_by_username, get_user_stats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = dt.datetime(2024, 6, 1, 12, 0, 0)


def _make_mock_coll():
    coll = AsyncMock()
    coll.count_documents = AsyncMock(return_value=0)
    coll.find_one = AsyncMock(return_value=None)
    # .find().to_list() chain
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=[])
    coll.find = MagicMock(return_value=cursor)
    # .aggregate().to_list() chain
    agg_cursor = AsyncMock()
    agg_cursor.to_list = AsyncMock(return_value=[])
    coll.aggregate = MagicMock(return_value=agg_cursor)
    return coll


def _patch_collections(**colls):
    """Return a context manager that patches get_collection.

    Each keyword arg maps a collection name to a mock collection.
    Unknown names return a generic mock.
    """
    defaults = {
        "users": _make_mock_coll(),
        "found_caches": _make_mock_coll(),
        "user_challenges": _make_mock_coll(),
        "cache_types": _make_mock_coll(),
    }
    defaults.update(colls)

    async def _get_collection(name):
        return defaults.get(name, _make_mock_coll())

    return patch("app.services.user_stats.get_collection", side_effect=_get_collection)


# ---------------------------------------------------------------------------
# get_user_stats — current user (no target_username)
# ---------------------------------------------------------------------------


class TestGetUserStatsSelf:
    @pytest.mark.asyncio
    async def test_basic_no_caches_no_challenges(self):
        user_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        with _patch_collections(users=users_coll):
            result = await get_user_stats(user_id)

        assert result.username == "alice"
        assert result.total_caches_found == 0
        assert result.total_challenges == 0
        assert result.cache_types_stats is None

    @pytest.mark.asyncio
    async def test_raises_if_current_user_not_found(self):
        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=None)

        with _patch_collections(users=users_coll):
            with pytest.raises(ValueError, match="not found"):
                await get_user_stats(ObjectId())

    @pytest.mark.asyncio
    async def test_last_activity_uses_max_of_cache_and_challenge(self):
        user_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        early = dt.datetime(2024, 1, 1)
        late = dt.datetime(2024, 5, 1)

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        found_caches_coll = _make_mock_coll()
        found_caches_coll.find_one = AsyncMock(
            side_effect=[
                {"found_date": early},  # first cache (ASCENDING)
                {"found_date": early},  # last cache (DESCENDING)
            ]
        )

        challenges_coll = _make_mock_coll()
        challenges_coll.find_one = AsyncMock(return_value={"created_at": late})

        with _patch_collections(
            users=users_coll,
            found_caches=found_caches_coll,
            user_challenges=challenges_coll,
        ):
            result = await get_user_stats(user_id)

        assert result.last_activity_at == late
        assert result.first_cache_found_at == early

    @pytest.mark.asyncio
    async def test_last_activity_none_when_no_caches_and_no_challenges(self):
        user_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        with _patch_collections(users=users_coll):
            result = await get_user_stats(user_id)

        assert result.last_activity_at is None


# ---------------------------------------------------------------------------
# get_user_stats — with target_username (admin path)
# ---------------------------------------------------------------------------


class TestGetUserStatsAdmin:
    @pytest.mark.asyncio
    async def test_admin_can_view_other_user_stats(self):
        admin_id = ObjectId()
        target_id = ObjectId()

        admin_doc = {"_id": admin_id, "role": "admin"}
        target_doc = {
            "_id": target_id,
            "username": "bob",
            "created_at": _NOW,
        }

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(side_effect=[admin_doc, target_doc])

        with _patch_collections(users=users_coll):
            result = await get_user_stats(admin_id, target_username="bob")

        assert result.username == "bob"

    @pytest.mark.asyncio
    async def test_non_admin_raises_permission_error(self):
        user_id = ObjectId()
        non_admin = {"_id": user_id, "role": "user"}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=non_admin)

        with _patch_collections(users=users_coll):
            with pytest.raises(PermissionError, match="Admin"):
                await get_user_stats(user_id, target_username="bob")

    @pytest.mark.asyncio
    async def test_raises_when_target_user_not_found(self):
        admin_id = ObjectId()
        admin_doc = {"_id": admin_id, "role": "admin"}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(side_effect=[admin_doc, None])

        with _patch_collections(users=users_coll):
            with pytest.raises(ValueError, match="not found"):
                await get_user_stats(admin_id, target_username="ghost")


# ---------------------------------------------------------------------------
# get_user_stats — cache_types_stats aggregation path
# ---------------------------------------------------------------------------


class TestGetUserStatsCacheTypeStats:
    @pytest.mark.asyncio
    async def test_populates_cache_type_stats(self):
        user_id = ObjectId()
        type_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        # found_caches aggregate returns one row with a type_id
        fc_agg_cursor = AsyncMock()
        fc_agg_cursor.to_list = AsyncMock(return_value=[{"_id": type_id, "count": 5}])
        found_caches_coll = _make_mock_coll()
        found_caches_coll.aggregate = MagicMock(return_value=fc_agg_cursor)

        # cache_types.find() returns matching type
        ct_cursor = AsyncMock()
        ct_cursor.to_list = AsyncMock(
            return_value=[{"_id": type_id, "name": "Traditional", "code": "TRAD"}]
        )
        cache_types_coll = _make_mock_coll()
        cache_types_coll.find = MagicMock(return_value=ct_cursor)

        with _patch_collections(
            users=users_coll,
            found_caches=found_caches_coll,
            cache_types=cache_types_coll,
        ):
            result = await get_user_stats(user_id)

        assert result.cache_types_stats is not None
        assert len(result.cache_types_stats) == 1
        assert result.cache_types_stats[0].type_label == "Traditional"
        assert result.cache_types_stats[0].count == 5

    @pytest.mark.asyncio
    async def test_not_found_types_appended_with_zero_count(self):
        """Types that appear in cache_types but not in found caches get count=0."""
        user_id = ObjectId()
        found_type_id = ObjectId()
        unfound_type_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        fc_agg_cursor = AsyncMock()
        fc_agg_cursor.to_list = AsyncMock(return_value=[{"_id": found_type_id, "count": 3}])
        found_caches_coll = _make_mock_coll()
        found_caches_coll.aggregate = MagicMock(return_value=fc_agg_cursor)

        ct_cursor = AsyncMock()
        ct_cursor.to_list = AsyncMock(
            return_value=[
                {"_id": found_type_id, "name": "Traditional", "code": "TRAD"},
                {"_id": unfound_type_id, "name": "Mystery", "code": "MYST"},
            ]
        )
        cache_types_coll = _make_mock_coll()
        cache_types_coll.find = MagicMock(return_value=ct_cursor)

        with _patch_collections(
            users=users_coll,
            found_caches=found_caches_coll,
            cache_types=cache_types_coll,
        ):
            result = await get_user_stats(user_id)

        labels = {s.type_label: s.count for s in result.cache_types_stats}
        assert labels["Traditional"] == 3
        assert labels["Mystery"] == 0

    @pytest.mark.asyncio
    async def test_cache_types_stats_none_when_aggregate_returns_empty(self):
        user_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        # aggregate returns an empty list → type_counts[0]["_id"] check is skipped
        with _patch_collections(users=users_coll):
            result = await get_user_stats(user_id)

        assert result.cache_types_stats is None

    @pytest.mark.asyncio
    async def test_cache_types_stats_none_when_type_ids_empty(self):
        """Aggregate row with _id=None → type_ids list is empty → no cache_types lookup."""
        user_id = ObjectId()
        user_doc = {"_id": user_id, "username": "alice", "created_at": _NOW}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        fc_agg_cursor = AsyncMock()
        fc_agg_cursor.to_list = AsyncMock(return_value=[{"_id": None, "count": 2}])
        found_caches_coll = _make_mock_coll()
        found_caches_coll.aggregate = MagicMock(return_value=fc_agg_cursor)

        with _patch_collections(users=users_coll, found_caches=found_caches_coll):
            result = await get_user_stats(user_id)

        assert result.cache_types_stats is None


# ---------------------------------------------------------------------------
# get_user_by_username
# ---------------------------------------------------------------------------


class TestGetUserByUsername:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        oid = ObjectId()
        user_doc = {"_id": oid, "username": "alice"}

        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=user_doc)

        with patch(
            "app.services.user_stats.get_collection",
            return_value=users_coll,
        ):
            result = await get_user_by_username("alice")

        assert result == user_doc

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        users_coll = _make_mock_coll()
        users_coll.find_one = AsyncMock(return_value=None)

        with patch(
            "app.services.user_stats.get_collection",
            return_value=users_coll,
        ):
            result = await get_user_by_username("ghost")

        assert result is None
