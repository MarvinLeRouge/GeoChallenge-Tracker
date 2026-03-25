"""Tests for TargetEvaluator."""

from unittest.mock import AsyncMock, MagicMock

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
