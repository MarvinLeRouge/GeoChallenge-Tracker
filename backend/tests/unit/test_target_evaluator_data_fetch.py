"""Tests for TargetEvaluator: get_username, get_latest_progress_task_map, get_user_challenge_tasks."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.targets.target_evaluator import TargetEvaluator
from tests.unit._target_evaluator_test_helpers import (
    _make_cursor,
    _make_db,
)


class TestGetUsername:
    @pytest.mark.asyncio
    async def test_returns_username_when_found(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value={"_id": ObjectId(), "username": "alice"})

        ev = TargetEvaluator(db)
        result = await ev.get_username(ObjectId())
        assert result == "alice"

    @pytest.mark.asyncio
    async def test_returns_none_when_user_not_found(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value=None)

        ev = TargetEvaluator(db)
        result = await ev.get_username(ObjectId())
        assert result is None


class TestGetLatestProgressTaskMap:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_progress(self):
        db = _make_db()
        db.progress.find_one = AsyncMock(return_value=None)

        ev = TargetEvaluator(db)
        result = await ev.get_latest_progress_task_map(ObjectId())
        assert result == {}

    @pytest.mark.asyncio
    async def test_builds_task_map_from_progress(self):
        task_id = ObjectId()
        db = _make_db()
        db.progress.find_one = AsyncMock(
            return_value={
                "_id": ObjectId(),
                "tasks": [
                    {"task_id": task_id, "current_count": 5},
                    {"task_id": None},  # should be skipped
                ],
            }
        )

        ev = TargetEvaluator(db)
        result = await ev.get_latest_progress_task_map(ObjectId())
        assert task_id in result
        assert result[task_id]["current_count"] == 5
        assert len(result) == 1  # None task_id skipped


class TestGetUserChallengeTasks:
    @pytest.mark.asyncio
    async def test_returns_task_list(self):
        task_id = ObjectId()
        db = _make_db()
        cursor = _make_cursor([{"_id": task_id, "title": "Task 1"}])
        db.user_challenge_tasks.find = MagicMock(return_value=cursor)

        ev = TargetEvaluator(db)
        result = await ev.get_user_challenge_tasks(ObjectId())
        assert len(result) == 1
        assert result[0]["_id"] == task_id

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tasks(self):
        db = _make_db()
        cursor = _make_cursor([])
        db.user_challenge_tasks.find = MagicMock(return_value=cursor)

        ev = TargetEvaluator(db)
        result = await ev.get_user_challenge_tasks(ObjectId())
        assert result == []
