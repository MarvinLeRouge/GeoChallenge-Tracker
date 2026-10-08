"""Tests for TargetEvaluator: build_cache_pipeline_for_task (incl. expression branches)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.targets.target_evaluator import TargetEvaluator
from tests.unit._target_evaluator_test_helpers import (
    _make_db,
)


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
