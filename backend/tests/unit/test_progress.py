"""Tests for progress service (unit tests - no DB required).

Strategy: patch private helpers and get_collection with AsyncMock/MagicMock to
isolate business logic (percent calculations, status transitions, ETA math).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UID = ObjectId()
_UC_ID = ObjectId()
_TASK_ID = ObjectId()
_TASK_ID2 = ObjectId()


def _mock_collection(**kwargs) -> AsyncMock:
    """Build an AsyncMock that mimics a Motor collection."""
    coll = AsyncMock()
    for k, v in kwargs.items():
        setattr(coll, k, v)
    return coll


def _async_return(val):
    """Return an AsyncMock that resolves to val."""
    m = AsyncMock(return_value=val)
    return m


# ---------------------------------------------------------------------------
# _ensure_uc_owned
# ---------------------------------------------------------------------------


class TestEnsureUcOwned:
    """Test _ensure_uc_owned authorization check."""

    @pytest.mark.asyncio
    async def test_owned_returns_row(self):
        from app.services.progress import _ensure_uc_owned

        row = {"_id": _UC_ID}
        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=row)

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _ensure_uc_owned(_UID, _UC_ID)

        assert result == row

    @pytest.mark.asyncio
    async def test_not_owned_raises_permission_error(self):
        from app.services.progress import _ensure_uc_owned

        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=None)

        with patch("app.services.progress.get_collection", return_value=coll):
            with pytest.raises(PermissionError):
                await _ensure_uc_owned(_UID, _UC_ID)


# ---------------------------------------------------------------------------
# evaluate_progress — percent / status logic
# ---------------------------------------------------------------------------


def _make_task(
    task_id=None,
    status="todo",
    min_count=10,
    expression=None,
    order=1,
    title="Task",
):
    return {
        "_id": task_id or _TASK_ID,
        "status": status,
        "constraints": {"min_count": min_count},
        "expression": expression or {"kind": "placed_year", "year": 2020},
        "order": order,
        "title": title,
        "updated_at": None,
        "created_at": None,
        "start_found_at": None,
        "completed_at": None,
    }


def _patch_evaluate_deps(
    *,
    tasks,
    uc_status=None,
    uc_computed_status=None,
    compile_result=None,
    current_count=5,
    aggregate_total=None,
    first_found_date=None,
    nth_found_date=None,
    last_snapshot=None,
):
    """Build a context-manager stack that patches all evaluate_progress dependencies."""
    if compile_result is None:
        compile_result = ("and:test", {}, True, [], None)

    # Mock collections used directly inside evaluate_progress
    uc_coll = AsyncMock()
    uc_coll.find_one = AsyncMock(
        return_value={"status": uc_status, "computed_status": uc_computed_status}
    )
    uc_coll.update_one = AsyncMock(return_value=None)

    tasks_coll = AsyncMock()
    tasks_coll.update_one = AsyncMock(return_value=None)

    progress_coll = AsyncMock()
    if last_snapshot:
        progress_coll.find_one = AsyncMock(return_value=last_snapshot)
    else:
        progress_coll.find_one = AsyncMock(return_value=None)
    progress_coll.insert_one = AsyncMock(return_value=None)

    async def _get_coll(name):
        if name == "user_challenges":
            return uc_coll
        if name == "user_challenge_tasks":
            return tasks_coll
        if name == "progress":
            return progress_coll
        return AsyncMock()

    patches = [
        patch(
            "app.services.progress._ensure_uc_owned",
            new=AsyncMock(return_value={"_id": _UC_ID}),
        ),
        patch(
            "app.services.progress._get_tasks_for_uc",
            new=AsyncMock(return_value=tasks),
        ),
        patch("app.services.progress.get_collection", side_effect=_get_coll),
        patch("app.services.progress.compile_and_only", return_value=compile_result),
        patch(
            "app.services.progress._count_found_caches_matching",
            new=AsyncMock(return_value=current_count),
        ),
        patch(
            "app.services.progress._aggregate_total",
            new=AsyncMock(return_value=aggregate_total or 0),
        ),
        patch(
            "app.services.progress._first_found_date",
            new=AsyncMock(return_value=first_found_date),
        ),
        patch(
            "app.services.progress._nth_found_date",
            new=AsyncMock(return_value=nth_found_date),
        ),
    ]
    return patches


class TestEvaluateProgress:
    """Test evaluate_progress business logic."""

    @pytest.mark.asyncio
    async def test_returns_last_snapshot_when_completed_not_forced(self):
        """If UC is already completed and force=False, return last snapshot without recalc."""
        from app.services.progress import evaluate_progress

        last = {"user_challenge_id": _UC_ID, "aggregate": {"percent": 100.0}}
        patches = _patch_evaluate_deps(
            tasks=[],
            uc_computed_status="completed",
            last_snapshot=last,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID, force=False)

        assert result is last

    @pytest.mark.asyncio
    async def test_force_recalculates_even_when_completed(self):
        """With force=True, re-evaluates even if UC is completed."""
        from app.services.progress import evaluate_progress

        patches = _patch_evaluate_deps(
            tasks=[],
            uc_computed_status="completed",
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID, force=True)

        assert "aggregate" in result

    @pytest.mark.asyncio
    async def test_done_task_not_forced_uses_override_snap(self):
        """A task with status=done and force=False uses the override (100%) snap."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="done", min_count=10)
        patches = _patch_evaluate_deps(tasks=[task])
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["percent"] == 100.0
        assert snap["compiled_signature"] == "override:done"
        assert snap["current_count"] == 10  # set to min_count

    @pytest.mark.asyncio
    async def test_unsupported_expression_produces_zero_percent(self):
        """An OR/NOT expression that compile_and_only rejects → 0% snap."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=5)
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("unsupported:or-not", {}, False, ["or/not unsupported"], None),
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["percent"] == 0.0
        assert snap["supported_for_progress"] is False

    @pytest.mark.asyncio
    async def test_count_only_percent_calculation(self):
        """100*(bounded/min_count) — partial progress."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        patches = _patch_evaluate_deps(tasks=[task], current_count=6)
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        # bounded = min(6, 10) = 6 → 60%
        assert snap["percent"] == 60.0
        assert snap["current_count"] == 6
        assert snap["status"] == "todo"  # 6 < 10 → not done

    @pytest.mark.asyncio
    async def test_task_becomes_done_when_count_met(self):
        """When current >= min_count, task status becomes done."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        patches = _patch_evaluate_deps(tasks=[task], current_count=10)
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["status"] == "done"
        assert snap["percent"] == 100.0

    @pytest.mark.asyncio
    async def test_count_capped_at_min_count(self):
        """count_percent is capped: bounded = min(current, min_count)."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        patches = _patch_evaluate_deps(tasks=[task], current_count=15)
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["percent"] == 100.0
        assert snap["status"] == "done"

    @pytest.mark.asyncio
    async def test_no_min_count_always_100_percent(self):
        """min_count=0 means any count gives 100% (filter-only tasks)."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        patches = _patch_evaluate_deps(tasks=[task], current_count=3)
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["percent"] == 100.0
        assert snap["status"] == "done"

    @pytest.mark.asyncio
    async def test_aggregate_only_uses_aggregate_percent(self):
        """With min_count=0 and aggregate spec, final_percent = aggregate_percent."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        agg_spec = {"kind": "difficulty", "min_total": 100}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            current_count=5,
            aggregate_total=60,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        # aggregate_percent = 100 * 60/100 = 60.0
        assert snap["percent"] == 60.0

    @pytest.mark.asyncio
    async def test_aggregate_unit_altitude(self):
        """Altitude aggregates use 'meters' as unit."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        agg_spec = {"kind": "altitude", "min_total": 5000}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            aggregate_total=2500,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["aggregate"]["unit"] == "meters"

    @pytest.mark.asyncio
    async def test_aggregate_unit_distinct_countries(self):
        """distinct_countries aggregate uses 'countries' unit."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        agg_spec = {"kind": "distinct_countries", "min_total": 10}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            aggregate_total=3,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["aggregate"]["unit"] == "countries"

    @pytest.mark.asyncio
    async def test_count_and_aggregate_final_percent_is_min(self):
        """With both count and aggregate constraints, final_percent = min(count%, agg%)."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        agg_spec = {"kind": "difficulty", "min_total": 100}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            current_count=8,  # count_percent = 80%
            aggregate_total=90,  # agg_percent = 90%
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        # final_percent = min(80, 90) = 80%
        assert snap["percent"] == 80.0

    @pytest.mark.asyncio
    async def test_aggregate_not_met_keeps_status_todo(self):
        """Task is not done if aggregate target is not met, even if count is met."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        agg_spec = {"kind": "difficulty", "min_total": 100}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            current_count=10,  # count met
            aggregate_total=50,  # agg not met
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["status"] != "done"

    @pytest.mark.asyncio
    async def test_global_aggregate_zero_when_no_supported_tasks(self):
        """With no supported tasks, global percent = 0.0."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=5)
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("unsupported", {}, False, ["unsupported"], None),
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        assert result["aggregate"]["percent"] == 0.0
        assert result["aggregate"]["tasks_total"] == 0

    @pytest.mark.asyncio
    async def test_global_aggregate_percent_with_multiple_tasks(self):
        """Global percent = sum_current / sum_min * 100, rounded to 1 decimal."""
        from app.services.progress import evaluate_progress

        t1 = _make_task(_TASK_ID, min_count=10)
        t2 = _make_task(_TASK_ID2, min_count=20, order=2, title="Task2")

        call_count = [0]

        async def _mock_count(*args, **kwargs):
            call_count[0] += 1
            return 5 if call_count[0] == 1 else 10  # t1: 5/10, t2: 10/20

        patches = _patch_evaluate_deps(tasks=[t1, t2])
        patches_with_count = patches[:-5] + [
            patch(
                "app.services.progress._count_found_caches_matching",
                side_effect=_mock_count,
            ),
            patch(
                "app.services.progress._aggregate_total",
                new=AsyncMock(return_value=0),
            ),
            patch(
                "app.services.progress._first_found_date",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.progress._nth_found_date",
                new=AsyncMock(return_value=None),
            ),
        ]
        with _apply_patches(patches_with_count):
            result = await evaluate_progress(_UID, _UC_ID)

        # sum_current = min(5,10) + min(10,20) = 5 + 10 = 15
        # sum_min = 10 + 20 = 30
        # aggregate_percent = round(100 * 15/30, 1) = 50.0
        assert result["aggregate"]["percent"] == 50.0


# ---------------------------------------------------------------------------
# get_latest_and_history — ETA logic
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# evaluate_new_progress — filtering logic
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Internal helpers for Motor mock
# ---------------------------------------------------------------------------


def _make_cursor(items: list) -> MagicMock:
    """Build a synchronous-chain mock that behaves like a Motor cursor for find()."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


def _make_async_iter(items: list) -> MagicMock:
    """Build a mock that supports 'async for' iteration (for progress.find())."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)

    # support async for: __aiter__ and __anext__
    async def _aiter(self):
        for item in items:
            yield item

    cursor.__aiter__ = lambda self: _aiter(self).__aiter__()
    return cursor


class _apply_patches:
    """Context manager that applies a list of patch objects."""

    def __init__(self, patches):
        self._patches = patches
        self._mocks = []

    def __enter__(self):
        for p in self._patches:
            self._mocks.append(p.start())
        return self._mocks

    def __exit__(self, *args):
        for p in self._patches:
            p.stop()
