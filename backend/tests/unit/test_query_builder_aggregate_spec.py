"""Tests for query_builder module: _extract_aggregate_spec (unit tests - no DB required)."""

from __future__ import annotations

from app.services.query_builder import _extract_aggregate_spec


class TestExtractAggregateSpec:
    """Test _extract_aggregate_spec aggregate extraction."""

    def test_no_aggregate(self):
        leaves = [{"kind": "placed_year", "year": 2020}]
        agg, remaining = _extract_aggregate_spec(leaves)
        assert agg is None
        assert remaining == leaves

    def test_difficulty_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_difficulty_at_least", "min_total": 50}
        leaves = [{"kind": "placed_year", "year": 2020}, agg_leaf]
        agg, remaining = _extract_aggregate_spec(leaves)
        assert agg == {"kind": "difficulty", "min_total": 50}
        assert remaining == [{"kind": "placed_year", "year": 2020}]

    def test_terrain_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_terrain_at_least", "min_total": 30}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "terrain", "min_total": 30}

    def test_diff_plus_terr_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_diff_plus_terr_at_least", "min_total": 100}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "diff_plus_terr", "min_total": 100}

    def test_altitude_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_altitude_at_least", "min_total": 5000}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "altitude", "min_total": 5000}

    def test_distinct_countries_aggregate(self):
        agg_leaf = {"kind": "aggregate_count_distinct_countries_at_least", "min_total": 10}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "distinct_countries", "min_total": 10}

    def test_dt_matrix_aggregate_default(self):
        agg_leaf = {"kind": "aggregate_dt_matrix_complete"}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg is not None
        assert agg["kind"] == "dt_matrix"
        assert agg["max_difficulty"] == 5.0
        assert agg["max_terrain"] == 5.0
        # 5.0 -> n = round((5.0-1.0)/0.5)+1 = 9, 9*9 = 81
        assert agg["min_total"] == 81

    def test_dt_matrix_aggregate_custom(self):
        agg_leaf = {
            "kind": "aggregate_dt_matrix_complete",
            "max_difficulty": 3.0,
            "max_terrain": 2.0,
        }
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg is not None
        # n_d = round((3.0-1.0)/0.5)+1 = 5, n_t = round((2.0-1.0)/0.5)+1 = 3
        assert agg["min_total"] == 5 * 3

    def test_only_first_aggregate_is_kept(self):
        agg1 = {"kind": "aggregate_sum_difficulty_at_least", "min_total": 50}
        agg2 = {"kind": "aggregate_sum_terrain_at_least", "min_total": 30}
        agg, remaining = _extract_aggregate_spec([agg1, agg2])
        assert agg == {"kind": "difficulty", "min_total": 50}
        # Second aggregate is dropped from remaining but not moved to agg
        assert len(remaining) == 0

    def test_aggregate_missing_min_total_ignored(self):
        agg_leaf = {"kind": "aggregate_sum_difficulty_at_least"}  # no min_total
        agg, remaining = _extract_aggregate_spec([agg_leaf])
        assert agg is None
        assert remaining == []  # leaf was consumed but agg is None
