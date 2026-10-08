"""Tests for TargetEvaluator: evaluate_cache_candidates and get_covered_dt_cells."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.targets.target_evaluator import TargetEvaluator
from tests.unit._target_evaluator_test_helpers import (
    _make_cursor,
    _make_db,
)


class TestEvaluateCacheCandidates:
    @pytest.mark.asyncio
    async def test_empty_tasks_returns_empty_dict(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        result = await ev.evaluate_cache_candidates(
            tasks=[],
            progress_map={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
            hard_limit_total=100,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_non_and_tasks(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        tasks = [
            {"_id": ObjectId(), "expression": {"kind": "or", "nodes": []}},
            {"_id": ObjectId(), "expression": {}},
        ]

        result = await ev.evaluate_cache_candidates(
            tasks=tasks,
            progress_map={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
            hard_limit_total=100,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_processes_and_tasks_with_results(self):
        db = _make_db()
        cache_id = ObjectId()
        task_id = ObjectId()

        cache_row = {"_id": cache_id, "title": "Cache 1"}
        agg_cursor = AsyncMock()
        agg_cursor.to_list = AsyncMock(return_value=[cache_row])
        db.caches.aggregate = MagicMock(return_value=agg_cursor)

        ev = TargetEvaluator(db)
        ev.scorer.get_task_constraints_min_count = MagicMock(return_value=5)

        tasks = [{"_id": task_id, "expression": {"kind": "and"}}]

        result = await ev.evaluate_cache_candidates(
            tasks=tasks,
            progress_map={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
            hard_limit_total=100,
        )

        assert cache_id in result
        assert result[cache_id]["matched_tasks"][0]["_id"] == task_id

    @pytest.mark.asyncio
    async def test_hard_limit_stops_processing(self):
        db = _make_db()
        task_id = ObjectId()

        # Two tasks, each returning a unique cache, but hard_limit_total=1
        cache_id1 = ObjectId()
        cache_id2 = ObjectId()

        call_count = [0]

        def make_cursor(*args, **kwargs):
            call_count[0] += 1
            cursor = AsyncMock()
            cursor.to_list = AsyncMock(
                return_value=[{"_id": cache_id1 if call_count[0] == 1 else cache_id2}]
            )
            return cursor

        db.caches.aggregate = MagicMock(side_effect=make_cursor)

        ev = TargetEvaluator(db)
        ev.scorer.get_task_constraints_min_count = MagicMock(return_value=1)

        tasks = [
            {"_id": task_id, "expression": {"kind": "and"}},
            {"_id": ObjectId(), "expression": {"kind": "and"}},
        ]

        result = await ev.evaluate_cache_candidates(
            tasks=tasks,
            progress_map={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
            hard_limit_total=1,  # stop after first unique cache
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_skips_completed_task(self):
        """Tasks with percent=100 should be skipped entirely."""
        db = _make_db()
        task_id = ObjectId()
        db.caches.aggregate = MagicMock(return_value=_make_cursor([]))

        ev = TargetEvaluator(db)
        tasks = [{"_id": task_id, "expression": {"kind": "and"}}]
        progress_map = {task_id: {"percent": 100}}

        result = await ev.evaluate_cache_candidates(
            tasks=tasks,
            progress_map=progress_map,
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
            hard_limit_total=100,
        )

        assert result == {}
        db.caches.aggregate.assert_not_called()


class TestGetCoveredDtCells:
    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_found_caches(self):
        db = _make_db()
        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        ev = TargetEvaluator(db)
        result = await ev._get_covered_dt_cells(
            user_id=ObjectId(),
            match_filters={},
            agg_spec={"max_difficulty": 3.0, "max_terrain": 3.0},
        )

        assert result == set()

    @pytest.mark.asyncio
    async def test_returns_covered_pairs_within_bounds(self):
        db = _make_db()
        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(
            return_value=[
                {"_id": {"d": 1.0, "t": 1.0}},
                {"_id": {"d": 2.0, "t": 2.0}},
                {"_id": {"d": 5.0, "t": 5.0}},  # out of bounds (max=3)
            ]
        )
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        ev = TargetEvaluator(db)
        result = await ev._get_covered_dt_cells(
            user_id=ObjectId(),
            match_filters={},
            agg_spec={"max_difficulty": 3.0, "max_terrain": 3.0},
        )

        assert (1.0, 1.0) in result
        assert (2.0, 2.0) in result
        assert (5.0, 5.0) not in result

    @pytest.mark.asyncio
    async def test_skips_rows_with_none_values(self):
        db = _make_db()
        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(
            return_value=[{"_id": {"d": None, "t": 1.0}}, {"_id": {"d": 1.0, "t": None}}]
        )
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        ev = TargetEvaluator(db)
        result = await ev._get_covered_dt_cells(
            user_id=ObjectId(),
            match_filters={},
            agg_spec={"max_difficulty": 3.0, "max_terrain": 3.0},
        )

        assert result == set()

    @pytest.mark.asyncio
    async def test_applies_match_filters_with_list_condition(self):
        """match_filters with list values should generate multiple $and conditions."""
        db = _make_db()
        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        ev = TargetEvaluator(db)
        await ev._get_covered_dt_cells(
            user_id=ObjectId(),
            match_filters={"type_id": [{"$in": ["id1"]}, {"$nin": ["id2"]}]},
            agg_spec={"max_difficulty": 3.0, "max_terrain": 3.0},
        )

        pipeline_used = db.found_caches.aggregate.call_args[0][0]
        and_stage = next(
            (s["$match"]["$and"] for s in pipeline_used if "$match" in s and "$and" in s["$match"]),
            None,
        )
        assert and_stage is not None
        assert any("cache.type_id" in c for c in and_stage)

    @pytest.mark.asyncio
    async def test_applies_match_filters_with_scalar_condition(self):
        """match_filters with scalar values should generate a single $and condition."""
        db = _make_db()
        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        type_id = ObjectId()
        ev = TargetEvaluator(db)
        await ev._get_covered_dt_cells(
            user_id=ObjectId(),
            match_filters={"type_id": type_id},
            agg_spec={"max_difficulty": 3.0, "max_terrain": 3.0},
        )

        pipeline_used = db.found_caches.aggregate.call_args[0][0]
        and_stage = next(
            (s["$match"]["$and"] for s in pipeline_used if "$match" in s and "$and" in s["$match"]),
            None,
        )
        assert and_stage is not None
        assert {"cache.type_id": type_id} in and_stage
