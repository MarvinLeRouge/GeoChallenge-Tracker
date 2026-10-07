"""Tests for progress.py: get_latest_and_history / ETA computation (and its missing-branch edge cases)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from tests.unit._progress_test_helpers import (
    _TASK_ID,
    _TASK_ID2,
    _UC_ID,
    _UID,
    _make_cursor,
)


class TestGetLatestAndHistoryEta:
    """Test ETA calculation in get_latest_and_history."""

    @pytest.mark.asyncio
    async def test_eta_set_when_task_completed(self):
        """Completed task (done date set) gets a fixed ETA = the done date."""
        from app.services.progress import get_latest_and_history

        done_date = date(2025, 6, 15)
        latest = {
            "_id": ObjectId(),
            "user_challenge_id": _UC_ID,
            "checked_at": datetime(2025, 6, 20),
            "aggregate": {"percent": 100.0},
            "tasks": [
                {"task_id": _TASK_ID, "current_count": 10, "min_count": 10, "percent": 100.0}
            ],
        }
        task_doc = {
            "_id": _TASK_ID,
            "start_found_at": date(2025, 1, 1),
            "completed_at": done_date,
            "constraints": {"min_count": 10},
        }

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                items = [latest]
                mock_cursor = _make_cursor(items)
                coll.find = MagicMock(return_value=mock_cursor)
            elif name == "user_challenge_tasks":
                mock_cursor = _make_cursor([task_doc])
                coll.find = MagicMock(return_value=mock_cursor)
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        task_snap = result["latest"]["tasks"][0]
        expected_eta = datetime(2025, 6, 15)
        assert task_snap["estimated_completion_at"] == expected_eta

    @pytest.mark.asyncio
    async def test_eta_none_when_no_start(self):
        """No start date → ETA is None."""
        from app.services.progress import get_latest_and_history

        latest = {
            "_id": ObjectId(),
            "user_challenge_id": _UC_ID,
            "checked_at": datetime(2025, 6, 20),
            "aggregate": {},
            "tasks": [{"task_id": _TASK_ID, "current_count": 3, "min_count": 10, "percent": 30.0}],
        }
        task_doc = {
            "_id": _TASK_ID,
            "start_found_at": None,
            "completed_at": None,
            "constraints": {"min_count": 10},
        }

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                coll.find = MagicMock(return_value=_make_cursor([latest]))
            elif name == "user_challenge_tasks":
                coll.find = MagicMock(return_value=_make_cursor([task_doc]))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        task_snap = result["latest"]["tasks"][0]
        assert task_snap["estimated_completion_at"] is None

    @pytest.mark.asyncio
    async def test_eta_extrapolation_in_progress(self):
        """ETA is extrapolated from speed when in progress."""
        from app.services.progress import get_latest_and_history

        # Fix "now" so the test is deterministic
        frozen_now = datetime(2025, 7, 1, 12, 0, 0)
        # start as datetime (MongoDB returns datetime, not date)
        start = datetime(2025, 6, 1, 0, 0, 0)  # 30 days ago
        current_count = 10
        min_count = 20
        # speed = (10-1) / 30 = 0.3/day, remaining = 10, eta_days = ceil(10/0.3) = 34
        elapsed = max((frozen_now.date() - start.date()).days, 1)
        speed = float(current_count - 1) / float(elapsed)
        remaining = max(0, min_count - current_count)
        expected_eta_days = math.ceil(remaining / speed)
        expected_eta_date = frozen_now.date() + timedelta(days=expected_eta_days)
        expected_eta = datetime(
            expected_eta_date.year, expected_eta_date.month, expected_eta_date.day
        )

        latest = {
            "_id": ObjectId(),
            "user_challenge_id": _UC_ID,
            "checked_at": frozen_now,
            "aggregate": {},
            "tasks": [
                {"task_id": _TASK_ID, "current_count": current_count, "min_count": min_count}
            ],
        }
        task_doc = {
            "_id": _TASK_ID,
            "start_found_at": start,  # datetime as returned by MongoDB
            "completed_at": None,
            "constraints": {"min_count": min_count},
        }

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                coll.find = MagicMock(return_value=_make_cursor([latest]))
            elif name == "user_challenge_tasks":
                coll.find = MagicMock(return_value=_make_cursor([task_doc]))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
            patch("app.services.progress.now", return_value=frozen_now),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        task_snap = result["latest"]["tasks"][0]
        assert task_snap["estimated_completion_at"] == expected_eta

    @pytest.mark.asyncio
    async def test_global_eta_is_max_of_task_etas(self):
        """Global ETA = max of all non-None per-task ETAs."""
        from app.services.progress import get_latest_and_history

        done1 = date(2025, 8, 1)
        done2 = date(2025, 9, 15)  # later

        latest = {
            "_id": ObjectId(),
            "user_challenge_id": _UC_ID,
            "checked_at": datetime(2025, 7, 1),
            "aggregate": {},
            "tasks": [
                {"task_id": _TASK_ID, "current_count": 5, "min_count": 5},
                {"task_id": _TASK_ID2, "current_count": 3, "min_count": 3},
            ],
        }
        task_docs = [
            {
                "_id": _TASK_ID,
                "start_found_at": done1,
                "completed_at": done1,
                "constraints": {"min_count": 5},
            },
            {
                "_id": _TASK_ID2,
                "start_found_at": done2,
                "completed_at": done2,
                "constraints": {"min_count": 3},
            },
        ]

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                coll.find = MagicMock(return_value=_make_cursor([latest]))
            elif name == "user_challenge_tasks":
                coll.find = MagicMock(return_value=_make_cursor(task_docs))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        # global ETA = max(done1, done2) = done2
        assert result["latest"]["estimated_completion_at"] == datetime(2025, 9, 15)

    @pytest.mark.asyncio
    async def test_no_snapshots_returns_none_latest(self):
        """When no snapshots exist, latest is None and history is empty."""
        from app.services.progress import get_latest_and_history

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                coll.find = MagicMock(return_value=_make_cursor([]))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        assert result["latest"] is None
        assert result["history"] == []


class TestGetLatestAndHistoryMissingBranches:
    @pytest.mark.asyncio
    async def test_before_filter_applied(self):
        """Passing before= adds $lt filter to the query (line 561)."""
        from app.services.progress import get_latest_and_history

        before = datetime(2025, 7, 1)

        async def _get_coll(name):
            coll = AsyncMock()
            coll.find = MagicMock(return_value=_make_cursor([]))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID, before=before)

        assert result["latest"] is None

    @pytest.mark.asyncio
    async def test_history_summarizes_older_snapshots(self):
        """With ≥2 snapshots, _summarize is called on history items (line 626)."""
        from app.services.progress import get_latest_and_history

        snap1 = {
            "_id": ObjectId(),
            "checked_at": datetime(2025, 7, 1),
            "aggregate": {"percent": 100.0},
            "tasks": [],
        }
        snap2 = {
            "_id": ObjectId(),
            "checked_at": datetime(2025, 6, 1),
            "aggregate": {"percent": 50.0},
            "tasks": [],
        }

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "progress":
                coll.find = MagicMock(return_value=_make_cursor([snap1, snap2]))
            elif name == "user_challenge_tasks":
                coll.find = MagicMock(return_value=_make_cursor([]))
            return coll

        with (
            patch("app.services.progress._ensure_uc_owned", new=AsyncMock(return_value={})),
            patch("app.services.progress.get_collection", side_effect=_get_coll),
        ):
            result = await get_latest_and_history(_UID, _UC_ID)

        assert len(result["history"]) == 1
        assert result["history"][0]["aggregate"] == snap2["aggregate"]
