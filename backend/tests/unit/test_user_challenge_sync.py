"""Tests for UserChallengeSync (unit — mocked DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.user_challenges.user_challenge_sync import UserChallengeSync

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncCursor:
    """Minimal async cursor supporting async-for."""

    def __init__(self, items):
        self._items = list(items)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


def _make_sync(**kwargs) -> tuple[UserChallengeSync, MagicMock]:
    db = MagicMock()

    db.challenges.distinct = AsyncMock(return_value=kwargs.get("challenge_ids", []))
    db.user_challenges.distinct = AsyncMock(return_value=kwargs.get("existing_ids", []))

    bulk_result = MagicMock()
    bulk_result.upserted_count = kwargs.get("upserted_count", 0)
    db.user_challenges.bulk_write = AsyncMock(return_value=bulk_result)

    db.user_challenges.aggregate.return_value = _AsyncCursor(kwargs.get("agg_docs", []))

    update_many_result = MagicMock()
    update_many_result.modified_count = kwargs.get("modified_count", 0)
    db.user_challenges.update_many = AsyncMock(return_value=update_many_result)

    db.user_challenges.count_documents = AsyncMock(return_value=kwargs.get("count", 0))

    update_one_result = MagicMock()
    update_one_result.modified_count = kwargs.get("update_one_modified", 0)
    db.user_challenges.update_one = AsyncMock(return_value=update_one_result)

    return UserChallengeSync(db), db


# ---------------------------------------------------------------------------
# _create_missing_user_challenges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_missing_no_challenges():
    sync, _ = _make_sync(challenge_ids=[])
    result = await sync._create_missing_user_challenges(ObjectId())
    assert result == {"created": 0, "existing": 0}


@pytest.mark.asyncio
async def test_create_missing_all_already_exist():
    cid = ObjectId()
    sync, db = _make_sync(challenge_ids=[cid], existing_ids=[cid])
    result = await sync._create_missing_user_challenges(ObjectId())
    assert result == {"created": 0, "existing": 1}
    db.user_challenges.bulk_write.assert_not_called()


@pytest.mark.asyncio
async def test_create_missing_new_ucs_inserted():
    cid = ObjectId()
    sync, db = _make_sync(challenge_ids=[cid], existing_ids=[], upserted_count=1)
    result = await sync._create_missing_user_challenges(ObjectId())
    assert result == {"created": 1, "existing": 0}
    db.user_challenges.bulk_write.assert_called_once()


@pytest.mark.asyncio
async def test_create_missing_partial_existing():
    cid1, cid2 = ObjectId(), ObjectId()
    sync, db = _make_sync(challenge_ids=[cid1, cid2], existing_ids=[cid1], upserted_count=1)
    result = await sync._create_missing_user_challenges(ObjectId())
    assert result["created"] == 1
    assert result["existing"] == 1


# ---------------------------------------------------------------------------
# _auto_complete_found_challenges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_complete_no_candidates():
    sync, db = _make_sync(agg_docs=[])
    result = await sync._auto_complete_found_challenges(ObjectId())
    assert result == {"updated": 0}
    db.user_challenges.update_many.assert_not_called()


@pytest.mark.asyncio
async def test_auto_complete_updates_found_challenges():
    uc_id = ObjectId()
    sync, db = _make_sync(agg_docs=[{"_id": uc_id}], modified_count=1)
    result = await sync._auto_complete_found_challenges(ObjectId())
    assert result["updated"] == 1
    db.user_challenges.update_many.assert_called_once()


@pytest.mark.asyncio
async def test_auto_complete_multiple_candidates():
    sync, db = _make_sync(
        agg_docs=[{"_id": ObjectId()}, {"_id": ObjectId()}],
        modified_count=2,
    )
    result = await sync._auto_complete_found_challenges(ObjectId())
    assert result["updated"] == 2


# ---------------------------------------------------------------------------
# _count_user_challenges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_user_challenges_returns_zero():
    sync, _ = _make_sync(count=0)
    assert await sync._count_user_challenges(ObjectId()) == 0


@pytest.mark.asyncio
async def test_count_user_challenges_returns_n():
    sync, _ = _make_sync(count=5)
    assert await sync._count_user_challenges(ObjectId()) == 5


# ---------------------------------------------------------------------------
# reset_user_challenge_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_found_returns_true():
    sync, _ = _make_sync(update_one_modified=1)
    result = await sync.reset_user_challenge_status(ObjectId(), ObjectId())
    assert result is True


@pytest.mark.asyncio
async def test_reset_not_found_returns_false():
    sync, _ = _make_sync(update_one_modified=0)
    result = await sync.reset_user_challenge_status(ObjectId(), ObjectId())
    assert result is False


# ---------------------------------------------------------------------------
# sync_user_challenges — orchestrator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_creates_missing_and_reports_stats():
    cid = ObjectId()
    sync, _ = _make_sync(
        challenge_ids=[cid],
        existing_ids=[],
        upserted_count=1,
        agg_docs=[],
        count=1,
    )
    result = await sync.sync_user_challenges(ObjectId())
    assert result["created"] == 1
    assert result["existing"] == 0
    assert result["auto_completed"] == 0
    assert result["total_user_challenges"] == 1


@pytest.mark.asyncio
async def test_sync_with_auto_completed():
    uc_id = ObjectId()
    sync, _ = _make_sync(
        challenge_ids=[],
        agg_docs=[{"_id": uc_id}],
        modified_count=1,
        count=3,
    )
    result = await sync.sync_user_challenges(ObjectId())
    assert result["created"] == 0
    assert result["auto_completed"] == 1
    assert result["total_user_challenges"] == 3
