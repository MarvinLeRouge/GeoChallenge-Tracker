"""Tests for TargetScorer and geo_utils pure functions (unit tests - no DB required)."""

from __future__ import annotations

import pytest

from app.services.targets.geo_utils import (
    build_geo_pipeline_stage,
    calculate_geo_score,
    haversine_distance_km,
)
from app.services.targets.target_scorer import TargetScorer

# ---------------------------------------------------------------------------
# haversine_distance_km
# ---------------------------------------------------------------------------


class TestHaversineDistanceKm:
    def test_same_point_zero_distance(self):
        assert haversine_distance_km(48.8566, 2.3522, 48.8566, 2.3522) == pytest.approx(
            0.0, abs=1e-6
        )

    def test_paris_to_london_approx(self):
        # ~340 km
        dist = haversine_distance_km(48.8566, 2.3522, 51.5074, -0.1278)
        assert 330 < dist < 350

    def test_symmetry(self):
        d1 = haversine_distance_km(48.0, 2.0, 43.0, 5.0)
        d2 = haversine_distance_km(43.0, 5.0, 48.0, 2.0)
        assert d1 == pytest.approx(d2, rel=1e-6)

    def test_antipodal_points_max_distance(self):
        dist = haversine_distance_km(0.0, 0.0, 0.0, 180.0)
        # Half circumference ≈ 20015 km
        assert 19000 < dist < 21000


# ---------------------------------------------------------------------------
# build_geo_pipeline_stage
# ---------------------------------------------------------------------------


class TestBuildGeoPipelineStage:
    def test_returns_geonear_stage(self):
        stage = build_geo_pipeline_stage(48.8566, 2.3522, 10.0)
        assert "$geoNear" in stage

    def test_coordinates_are_lon_lat(self):
        stage = build_geo_pipeline_stage(48.8566, 2.3522, 10.0)
        near = stage["$geoNear"]["near"]
        assert near["type"] == "Point"
        # GeoJSON is [lon, lat]
        assert near["coordinates"] == [2.3522, 48.8566]

    def test_max_distance_converted_to_meters(self):
        stage = build_geo_pipeline_stage(48.0, 2.0, 5.0)
        assert stage["$geoNear"]["maxDistance"] == 5000.0

    def test_spherical_is_true(self):
        stage = build_geo_pipeline_stage(0.0, 0.0, 1.0)
        assert stage["$geoNear"]["spherical"] is True


# ---------------------------------------------------------------------------
# calculate_geo_score
# ---------------------------------------------------------------------------


class TestCalculateGeoScore:
    def test_zero_distance_returns_one(self):
        assert calculate_geo_score(0.0, 10.0) == pytest.approx(1.0)

    def test_negative_distance_returns_one(self):
        assert calculate_geo_score(-5.0, 10.0) == pytest.approx(1.0)

    def test_score_decreases_with_distance(self):
        s1 = calculate_geo_score(1000.0, 10.0)
        s2 = calculate_geo_score(5000.0, 10.0)
        assert s1 > s2

    def test_score_between_zero_and_one(self):
        for dist in [0, 100, 1000, 10000, 100000]:
            score = calculate_geo_score(dist, 10.0)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# TargetScorer
# ---------------------------------------------------------------------------


class TestCalculateTaskUrgencyScore:
    def test_empty_tasks_returns_zero(self):
        assert TargetScorer.calculate_task_urgency_score([]) == 0.0

    def test_single_task_ratio(self):
        tasks = [{"ratio": 0.7}]
        assert TargetScorer.calculate_task_urgency_score(tasks) == pytest.approx(0.7)

    def test_capped_at_one(self):
        tasks = [{"ratio": 1.5}]
        assert TargetScorer.calculate_task_urgency_score(tasks) == pytest.approx(1.0)

    def test_max_ratio_used(self):
        tasks = [{"ratio": 0.3}, {"ratio": 0.9}, {"ratio": 0.5}]
        assert TargetScorer.calculate_task_urgency_score(tasks) == pytest.approx(0.9)

    def test_missing_ratio_defaults_to_zero(self):
        tasks = [{}]
        assert TargetScorer.calculate_task_urgency_score(tasks) == 0.0


class TestCalculateTaskCoverageScore:
    def test_zero_total_returns_zero(self):
        assert TargetScorer.calculate_task_coverage_score(5, 0) == 0.0

    def test_negative_total_returns_zero(self):
        assert TargetScorer.calculate_task_coverage_score(1, -1) == 0.0

    def test_full_coverage(self):
        assert TargetScorer.calculate_task_coverage_score(3, 3) == pytest.approx(1.0)

    def test_partial_coverage(self):
        assert TargetScorer.calculate_task_coverage_score(1, 4) == pytest.approx(0.25)

    def test_capped_at_one(self):
        assert TargetScorer.calculate_task_coverage_score(10, 3) == pytest.approx(1.0)


class TestChoosePrimaryTaskByRatio:
    def test_empty_returns_none(self):
        assert TargetScorer.choose_primary_task_by_ratio([]) is None

    def test_highest_ratio_selected(self):
        from bson import ObjectId

        oid1, oid2 = ObjectId(), ObjectId()
        tasks = [{"_id": oid1, "ratio": 0.3}, {"_id": oid2, "ratio": 0.8}]
        assert TargetScorer.choose_primary_task_by_ratio(tasks) == oid2

    def test_single_task(self):
        from bson import ObjectId

        oid = ObjectId()
        tasks = [{"_id": oid, "ratio": 0.5}]
        assert TargetScorer.choose_primary_task_by_ratio(tasks) == oid


class TestCalculateCompositeScore:
    def test_empty_tasks_all_zero(self):
        scores = TargetScorer.calculate_composite_score([], 5)
        assert scores["urgency"] == 0.0
        assert scores["coverage"] == 0.0
        assert scores["composite"] == pytest.approx(0.0)

    def test_without_geo_score(self):
        tasks = [{"ratio": 1.0}]
        scores = TargetScorer.calculate_composite_score(tasks, 1)
        assert scores["geographic"] == 0.0
        assert scores["composite"] > 0.0

    def test_with_geo_score(self):
        tasks = [{"ratio": 0.5}]
        scores = TargetScorer.calculate_composite_score(tasks, 2, distance_m=0.0, radius_km=10.0)
        assert scores["geographic"] == pytest.approx(1.0)

    def test_composite_capped_at_one(self):
        tasks = [{"ratio": 1.0}, {"ratio": 1.0}]
        scores = TargetScorer.calculate_composite_score(tasks, 1, distance_m=0.0, radius_km=1.0)
        assert scores["composite"] <= 1.0

    def test_custom_weights_applied(self):
        tasks = [{"ratio": 1.0}]
        scores = TargetScorer.calculate_composite_score(
            tasks, 1, weights={"urgency": 1.0, "coverage": 0.0, "geographic": 0.0}
        )
        assert scores["composite"] == pytest.approx(1.0)


class TestGetTaskConstraintsMinCount:
    def test_default_is_one(self):
        assert TargetScorer.get_task_constraints_min_count({}) == 1

    def test_explicit_min_count(self):
        task = {"constraints": {"min_count": 10}}
        assert TargetScorer.get_task_constraints_min_count(task) == 10

    def test_string_min_count_converted(self):
        task = {"constraints": {"min_count": "5"}}
        assert TargetScorer.get_task_constraints_min_count(task) == 5


# ---------------------------------------------------------------------------
# get_user_location (async, needs get_collection mocked)
# ---------------------------------------------------------------------------


class TestGetUserLocation:
    @pytest.mark.asyncio
    async def test_no_user_doc_returns_none(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from bson import ObjectId

        from app.services.targets.geo_utils import get_user_location

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value=None)
        with patch(
            "app.services.targets.geo_utils.get_collection", AsyncMock(return_value=mock_coll)
        ):
            result = await get_user_location(ObjectId())
        assert result is None

    @pytest.mark.asyncio
    async def test_user_doc_no_location_returns_none(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from bson import ObjectId

        from app.services.targets.geo_utils import get_user_location

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value={"_id": ObjectId()})
        with patch(
            "app.services.targets.geo_utils.get_collection", AsyncMock(return_value=mock_coll)
        ):
            result = await get_user_location(ObjectId())
        assert result is None

    @pytest.mark.asyncio
    async def test_location_not_point_returns_none(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from bson import ObjectId

        from app.services.targets.geo_utils import get_user_location

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value={"location": {"type": "LineString"}})
        with patch(
            "app.services.targets.geo_utils.get_collection", AsyncMock(return_value=mock_coll)
        ):
            result = await get_user_location(ObjectId())
        assert result is None

    @pytest.mark.asyncio
    async def test_coordinates_wrong_length_returns_none(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from bson import ObjectId

        from app.services.targets.geo_utils import get_user_location

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(
            return_value={"location": {"type": "Point", "coordinates": [2.35]}}
        )
        with patch(
            "app.services.targets.geo_utils.get_collection", AsyncMock(return_value=mock_coll)
        ):
            result = await get_user_location(ObjectId())
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_location_returns_lat_lon(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from bson import ObjectId

        from app.services.targets.geo_utils import get_user_location

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(
            return_value={"location": {"type": "Point", "coordinates": [2.3522, 48.8566]}}
        )
        with patch(
            "app.services.targets.geo_utils.get_collection", AsyncMock(return_value=mock_coll)
        ):
            result = await get_user_location(ObjectId())
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(48.8566)
        assert lon == pytest.approx(2.3522)
