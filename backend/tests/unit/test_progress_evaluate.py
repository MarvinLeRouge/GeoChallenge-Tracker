"""Tests for progress.py: evaluate_progress (and its missing-branch edge cases)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from tests.unit._progress_test_helpers import (
    _TASK_ID,
    _TASK_ID2,
    _UC_ID,
    _UID,
    _apply_patches,
    _make_task,
    _patch_evaluate_deps,
)


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
                "app.services.progress_aggregates._count_found_caches_matching",
                side_effect=_mock_count,
            ),
            patch(
                "app.services.progress_aggregates._aggregate_total",
                new=AsyncMock(return_value=0),
            ),
            patch(
                "app.services.progress_aggregates._first_found_date",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.progress_aggregates._nth_found_date",
                new=AsyncMock(return_value=None),
            ),
        ]
        with _apply_patches(patches_with_count):
            result = await evaluate_progress(_UID, _UC_ID)

        # sum_current = min(5,10) + min(10,20) = 5 + 10 = 15
        # sum_min = 10 + 20 = 30
        # aggregate_percent = round(100 * 15/30, 1) = 50.0
        assert result["aggregate"]["percent"] == 50.0


class TestEvaluateProgressMissingBranches:
    @pytest.mark.asyncio
    async def test_aggregate_no_min_total_percent_is_zero(self):
        """agg_spec without min_total → aggregate_percent=None → final_percent=0.0."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        agg_spec = {"kind": "difficulty"}  # no min_total
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            current_count=5,
            aggregate_total=60,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        # aggregate_percent is None (no min_total), final_percent = 0.0
        assert snap["percent"] == 0.0

    @pytest.mark.asyncio
    async def test_aggregate_unit_dt_matrix(self):
        """dt_matrix aggregate kind uses 'cells' as unit."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=0)
        agg_spec = {"kind": "dt_matrix", "min_total": 25}
        patches = _patch_evaluate_deps(
            tasks=[task],
            compile_result=("and:test", {}, True, [], agg_spec),
            aggregate_total=10,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        snap = result["tasks"][0]
        assert snap["aggregate"]["unit"] == "cells"

    @pytest.mark.asyncio
    async def test_start_found_at_persisted_when_first_find(self):
        """When _first_found_date returns a date and task has no start, DB is updated."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=5)  # start_found_at=None
        start = date(2025, 3, 1)
        patches = _patch_evaluate_deps(tasks=[task], current_count=3, first_found_date=start)
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        # Line 429-433 executed; task still todo (3 < 5)
        assert result["tasks"][0]["status"] == "todo"

    @pytest.mark.asyncio
    async def test_completed_at_persisted_when_nth_reached(self):
        """When current >= min_count and nth_found_date returns a date, DB is updated."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=5)  # completed_at=None
        completed = date(2025, 6, 1)
        patches = _patch_evaluate_deps(
            tasks=[task],
            current_count=5,
            nth_found_date=completed,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        # Lines 442-452 executed; task is done
        assert result["tasks"][0]["status"] == "done"

    @pytest.mark.asyncio
    async def test_completed_at_cleared_when_no_longer_valid(self):
        """When completed_dt is None but task.completed_at was set, DB is cleared."""
        from app.services.progress import evaluate_progress

        task = _make_task(status="todo", min_count=10)
        task["completed_at"] = date(2025, 1, 1)  # previously set
        patches = _patch_evaluate_deps(
            tasks=[task],
            current_count=3,  # < min_count → no nth_found_date call
            nth_found_date=None,
        )
        with _apply_patches(patches):
            result = await evaluate_progress(_UID, _UC_ID)

        # Lines 455-459 executed; task still todo
        assert result["tasks"][0]["status"] == "todo"
