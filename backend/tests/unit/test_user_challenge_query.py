"""Tests for UserChallengeQuery (unit — mocked DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.user_challenges.user_challenge_query import UserChallengeQuery

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncCursor:
    """Minimal async cursor supporting async-for, .next(), and .to_list()."""

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

    async def next(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item

    async def to_list(self, length=None):
        return self._items


def _count_cursor(total: int | None):
    cursor = MagicMock()
    if total is None:
        cursor.next = AsyncMock(side_effect=StopAsyncIteration)
    else:
        cursor.next = AsyncMock(return_value={"total": total})
    return cursor


def _make_query():
    db = MagicMock()
    return UserChallengeQuery(db), db


# ---------------------------------------------------------------------------
# _build_list_pipeline — pure method, no DB
# ---------------------------------------------------------------------------


def test_build_list_pipeline_no_filter():
    q, _ = _make_query()
    uid = ObjectId()
    pipeline = q._build_list_pipeline(uid, None)
    assert pipeline[0] == {"$match": {"user_id": uid}}


def test_build_list_pipeline_with_status_filter_adds_stages():
    q, _ = _make_query()
    uid = ObjectId()
    pipeline_no = q._build_list_pipeline(uid, None)
    # "pending" adds a $match stage (unlike "active" which is the default)
    pipeline_yes = q._build_list_pipeline(uid, "pending")
    assert len(pipeline_yes) > len(pipeline_no)


def test_build_list_pipeline_contains_lookup_and_sort():
    q, _ = _make_query()
    pipeline = q._build_list_pipeline(ObjectId(), None)
    keys = [list(s.keys())[0] for s in pipeline]
    assert "$lookup" in keys
    assert "$sort" in keys


# ---------------------------------------------------------------------------
# _count_filtered_user_challenges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_returns_zero_when_empty():
    q, db = _make_query()
    db.user_challenges.aggregate.return_value = _count_cursor(None)
    result = await q._count_filtered_user_challenges(ObjectId(), None)
    assert result == 0


@pytest.mark.asyncio
async def test_count_returns_total():
    q, db = _make_query()
    db.user_challenges.aggregate.return_value = _count_cursor(7)
    result = await q._count_filtered_user_challenges(ObjectId(), None)
    assert result == 7


@pytest.mark.asyncio
async def test_count_with_status_filter():
    q, db = _make_query()
    db.user_challenges.aggregate.return_value = _count_cursor(3)
    result = await q._count_filtered_user_challenges(ObjectId(), "active")
    assert result == 3


# ---------------------------------------------------------------------------
# list_user_challenges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty_returns_zero_items():
    q, db = _make_query()
    db.user_challenges.aggregate.side_effect = [
        _count_cursor(None),
        _AsyncCursor([]),
    ]
    result = await q.list_user_challenges(ObjectId())
    assert result["items"] == []
    assert result["nb_items"] == 0
    assert result["nb_pages"] == 0


@pytest.mark.asyncio
async def test_list_returns_items_with_effective_status_and_id():
    uid = ObjectId()
    uc_id = ObjectId()
    doc = {
        "_id": uc_id,
        "status": "active",
        "computed_status": None,
        "progress": {},
        "updated_at": None,
        "challenge": {"id": ObjectId(), "name": "Test"},
        "cache": None,
    }
    q, db = _make_query()
    db.user_challenges.aggregate.side_effect = [
        _count_cursor(1),
        _AsyncCursor([doc]),
    ]
    result = await q.list_user_challenges(uid)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert "effective_status" in item
    assert "id" in item
    assert "_id" not in item


@pytest.mark.asyncio
async def test_list_pagination_metadata():
    q, db = _make_query()
    db.user_challenges.aggregate.side_effect = [
        _count_cursor(25),
        _AsyncCursor([]),
    ]
    result = await q.list_user_challenges(ObjectId(), page=2, page_size=10)
    assert result["page"] == 2
    assert result["page_size"] == 10
    assert result["nb_items"] == 25
    assert result["nb_pages"] == 3


@pytest.mark.asyncio
async def test_list_with_status_filter():
    q, db = _make_query()
    db.user_challenges.aggregate.side_effect = [
        _count_cursor(2),
        _AsyncCursor([]),
    ]
    result = await q.list_user_challenges(ObjectId(), status_filter="active")
    assert result["nb_items"] == 2


# ---------------------------------------------------------------------------
# get_user_challenge_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detail_not_found():
    q, db = _make_query()
    cursor = MagicMock()
    cursor.next = AsyncMock(side_effect=StopAsyncIteration)
    db.user_challenges.aggregate.return_value = cursor
    result = await q.get_user_challenge_detail(ObjectId(), ObjectId())
    assert result is None


@pytest.mark.asyncio
async def test_get_detail_found_returns_enriched_doc():
    uc_id = ObjectId()
    doc = {
        "_id": uc_id,
        "status": "pending",
        "computed_status": None,
        "manual_override": False,
        "override_reason": None,
        "overridden_at": None,
        "notes": None,
        "progress": {},
        "created_at": None,
        "updated_at": None,
        "challenge": {"id": ObjectId(), "name": "My Challenge", "description": ""},
        "cache": None,
    }
    q, db = _make_query()
    cursor = MagicMock()
    cursor.next = AsyncMock(return_value=doc)
    db.user_challenges.aggregate.return_value = cursor
    result = await q.get_user_challenge_detail(ObjectId(), uc_id)
    assert result is not None
    assert result["id"] == str(uc_id)
    assert "_id" not in result
    assert "effective_status" in result
