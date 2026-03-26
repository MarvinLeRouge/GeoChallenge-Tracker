"""Tests for TargetEvaluator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.targets.target_evaluator import TargetEvaluator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    class MockDB:
        def __init__(self):
            self.users = AsyncMock()
            self.progress = AsyncMock()
            self.user_challenge_tasks = AsyncMock()
            self.caches = AsyncMock()
            self.found_caches = AsyncMock()

    return MockDB()


def _make_cursor(rows):
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=rows)
    return cursor


# ---------------------------------------------------------------------------
# get_username
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# get_latest_progress_task_map
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# get_user_challenge_tasks
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# build_cache_pipeline_for_task
# ---------------------------------------------------------------------------


class TestBuildCachePipelineForTask:
    @pytest.mark.asyncio
    async def test_pipeline_has_base_match(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
        )

        match_stages = [s for s in pipeline if "$match" in s]
        assert len(match_stages) >= 1

    @pytest.mark.asyncio
    async def test_excludes_caches_owned_by_user(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc={},
            username="alice",
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
        )

        base_match = next(s["$match"] for s in pipeline if "$match" in s)
        assert base_match.get("owner") == {"$ne": "alice"}

    @pytest.mark.asyncio
    async def test_adds_geo_near_stage_when_geo_ctx_provided(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        geo_ctx = {"lat": 48.85, "lon": 2.35, "radius_km": 5}
        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=geo_ctx,
            limit_per_task=10,
        )

        assert "$geoNear" in pipeline[0]
        # distance_m should appear in projection
        proj_stage = next((s for s in pipeline if "$project" in s), None)
        assert proj_stage is not None
        assert "distance_m" in proj_stage["$project"]

    @pytest.mark.asyncio
    async def test_applies_task_expression_filter(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        task_doc = {"expression": {"kind": "placed_year", "year": 2020}}

        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc=task_doc,
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
        )

        # Should have more than 2 match stages (base + expression)
        match_stages = [s for s in pipeline if "$match" in s]
        assert len(match_stages) >= 2

    @pytest.mark.asyncio
    async def test_skips_bad_expression_without_error(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        task_doc = {"expression": {"kind": "invalid_expression_that_will_fail"}}

        # Should not raise even if expression compilation fails
        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc=task_doc,
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=10,
        )

        assert pipeline is not None

    @pytest.mark.asyncio
    async def test_pipeline_ends_with_limit(self):
        db = _make_db()
        ev = TargetEvaluator(db)

        pipeline = await ev.build_cache_pipeline_for_task(
            task_doc={},
            username=None,
            user_id=ObjectId(),
            geo_ctx=None,
            limit_per_task=25,
        )

        limit_stage = next((s for s in pipeline if "$limit" in s), None)
        assert limit_stage is not None
        assert limit_stage["$limit"] == 25


# ---------------------------------------------------------------------------
# evaluate_cache_candidates
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# build_cache_pipeline_for_task — expression branches
# ---------------------------------------------------------------------------


class TestBuildCachePipelineExpressionBranches:
    @pytest.mark.asyncio
    async def test_compile_and_only_exception_is_handled(self):
        """If compile_and_only raises, pipeline is still returned without error."""
        db = _make_db()
        ev = TargetEvaluator(db)

        task_doc = {"expression": {"kind": "and", "rules": []}}

        with patch(
            "app.services.targets.target_evaluator.compile_and_only",
            side_effect=RuntimeError("compilation failed"),
        ):
            pipeline = await ev.build_cache_pipeline_for_task(
                task_doc=task_doc,
                username=None,
                user_id=ObjectId(),
                geo_ctx=None,
                limit_per_task=10,
            )

        assert pipeline is not None
        assert any("$limit" in s for s in pipeline)

    @pytest.mark.asyncio
    async def test_unsupported_expression_clears_agg_spec(self):
        """If compile_and_only returns supported=False, no dt_matrix stages are added."""
        db = _make_db()
        ev = TargetEvaluator(db)

        task_doc = {"expression": {"kind": "and", "rules": []}}

        with patch(
            "app.services.targets.target_evaluator.compile_and_only",
            return_value=(
                "sig",
                {},
                False,
                [],
                {"kind": "dt_matrix", "max_difficulty": 3.0, "max_terrain": 3.0},
            ),
        ):
            pipeline = await ev.build_cache_pipeline_for_task(
                task_doc=task_doc,
                username=None,
                user_id=ObjectId(),
                geo_ctx=None,
                limit_per_task=10,
            )

        # No D/T bounds match stage should be present
        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        dt_bounds = [m for m in match_stages if "difficulty" in m and "terrain" in m]
        assert dt_bounds == []

    @pytest.mark.asyncio
    async def test_dt_matrix_adds_bounds_stage(self):
        """dt_matrix agg_spec triggers D/T bounds $match stage."""
        db = _make_db()
        ev = TargetEvaluator(db)

        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(return_value=[])
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        task_doc = {"expression": {"kind": "and", "rules": []}}
        agg_spec = {"kind": "dt_matrix", "max_difficulty": 3.0, "max_terrain": 3.0}

        with patch(
            "app.services.targets.target_evaluator.compile_and_only",
            return_value=("sig", {}, True, [], agg_spec),
        ):
            pipeline = await ev.build_cache_pipeline_for_task(
                task_doc=task_doc,
                username=None,
                user_id=ObjectId(),
                geo_ctx=None,
                limit_per_task=10,
            )

        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        dt_bounds = [m for m in match_stages if "difficulty" in m and "terrain" in m]
        assert len(dt_bounds) == 1
        assert dt_bounds[0]["difficulty"] == {"$gte": 1.0, "$lte": 3.0}
        assert dt_bounds[0]["terrain"] == {"$gte": 1.0, "$lte": 3.0}

    @pytest.mark.asyncio
    async def test_dt_matrix_adds_nor_stage_for_covered_cells(self):
        """dt_matrix with covered cells adds a $nor exclusion stage."""
        db = _make_db()
        ev = TargetEvaluator(db)

        fc_cursor = AsyncMock()
        fc_cursor.to_list = AsyncMock(
            return_value=[{"_id": {"d": 1.0, "t": 1.0}}, {"_id": {"d": 1.5, "t": 1.5}}]
        )
        db.found_caches.aggregate = MagicMock(return_value=fc_cursor)

        task_doc = {"expression": {"kind": "and", "rules": []}}
        agg_spec = {"kind": "dt_matrix", "max_difficulty": 3.0, "max_terrain": 3.0}

        with patch(
            "app.services.targets.target_evaluator.compile_and_only",
            return_value=("sig", {}, True, [], agg_spec),
        ):
            pipeline = await ev.build_cache_pipeline_for_task(
                task_doc=task_doc,
                username=None,
                user_id=ObjectId(),
                geo_ctx=None,
                limit_per_task=10,
            )

        nor_stages = [
            s["$match"] for s in pipeline if "$match" in s and "$nor" in s.get("$match", {})
        ]
        assert len(nor_stages) == 1
        assert len(nor_stages[0]["$nor"]) == 2


# ---------------------------------------------------------------------------
# _get_covered_dt_cells
# ---------------------------------------------------------------------------


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
