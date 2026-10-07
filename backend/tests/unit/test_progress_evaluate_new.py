"""Tests for progress.py: evaluate_new_progress (and its missing-branch edge cases)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from tests.unit._progress_test_helpers import (
    _UID,
    _make_async_iter,
    _make_cursor,
)


class TestEvaluateNewProgress:
    """Test evaluate_new_progress UC filtering."""

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_zeros(self):
        from app.services.progress import evaluate_new_progress

        async def _get_coll(name):
            coll = AsyncMock()
            coll.find = MagicMock(return_value=_make_cursor([]))
            return coll

        with patch("app.services.progress.get_collection", side_effect=_get_coll):
            result = await evaluate_new_progress(_UID)

        assert result == {"evaluated_count": 0, "skipped_count": 0, "uc_ids": []}

    @pytest.mark.asyncio
    async def test_skips_uc_already_with_progress(self):
        from app.services.progress import evaluate_new_progress

        uc1 = ObjectId()
        uc2 = ObjectId()

        # progress already exists for uc1
        uc_cursor = _make_cursor([{"_id": uc1}, {"_id": uc2}])
        prog_cursor = _make_async_iter([{"user_challenge_id": uc1}])

        async def _get_coll(name):
            coll = AsyncMock()
            if name == "user_challenges":
                coll.find = MagicMock(return_value=uc_cursor)
            elif name == "progress":
                coll.find = MagicMock(return_value=prog_cursor)
            return coll

        with (
            patch("app.services.progress.get_collection", side_effect=_get_coll),
            patch(
                "app.services.progress.evaluate_progress",
                new=AsyncMock(return_value={}),
            ) as mock_eval,
        ):
            result = await evaluate_new_progress(_UID)

        # uc1 is skipped (has progress), only uc2 is evaluated
        assert result["evaluated_count"] == 1
        assert str(uc2) in result["uc_ids"]
        mock_eval.assert_awaited_once_with(_UID, uc2)


class TestEvaluateNewProgressMissingBranches:
    @pytest.mark.asyncio
    async def test_since_filter_applied(self):
        """Passing since= adds created_at $gte filter (line 669)."""
        from app.services.progress import evaluate_new_progress

        since = datetime(2025, 1, 1)

        async def _get_coll(name):
            coll = AsyncMock()
            coll.find = MagicMock(return_value=_make_cursor([]))
            return coll

        with patch("app.services.progress.get_collection", side_effect=_get_coll):
            result = await evaluate_new_progress(_UID, since=since)

        assert result == {"evaluated_count": 0, "skipped_count": 0, "uc_ids": []}
