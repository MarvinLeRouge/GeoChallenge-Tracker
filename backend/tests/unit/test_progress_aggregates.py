"""Tests for progress.py: count/aggregate/date-lookup helpers (_count_found_caches_matching, _aggregate_total, _nth_found_date, _first_found_date)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from tests.unit._progress_test_helpers import (
    _UID,
    _mock_aggregate_coll,
)


class TestCountFoundCachesMatching:
    @pytest.mark.asyncio
    async def test_no_conditions_returns_count(self):
        from app.services.progress_aggregates import _count_found_caches_matching

        coll = _mock_aggregate_coll([{"current_count": 7}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _count_found_caches_matching(_UID, {})
        assert result == 7

    @pytest.mark.asyncio
    async def test_single_condition(self):
        from app.services.progress_aggregates import _count_found_caches_matching

        coll = _mock_aggregate_coll([{"current_count": 3}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _count_found_caches_matching(_UID, {"difficulty": {"$gte": 3.0}})
        assert result == 3

    @pytest.mark.asyncio
    async def test_list_condition(self):
        from app.services.progress_aggregates import _count_found_caches_matching

        coll = _mock_aggregate_coll([{"current_count": 2}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _count_found_caches_matching(
                _UID, {"difficulty": [{"$gte": 3.0}, {"$lte": 5.0}]}
            )
        assert result == 2

    @pytest.mark.asyncio
    async def test_no_rows_returns_zero(self):
        from app.services.progress_aggregates import _count_found_caches_matching

        coll = _mock_aggregate_coll([])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _count_found_caches_matching(_UID, {})
        assert result == 0


class TestAggregateTotal:
    @pytest.mark.asyncio
    async def test_unknown_kind_returns_zero(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "unknown_kind"})
        assert result == 0

    @pytest.mark.asyncio
    async def test_difficulty_kind(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 42}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "difficulty"})
        assert result == 42

    @pytest.mark.asyncio
    async def test_terrain_kind(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 15}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "terrain"})
        assert result == 15

    @pytest.mark.asyncio
    async def test_diff_plus_terr_kind(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 30}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "diff_plus_terr"})
        assert result == 30

    @pytest.mark.asyncio
    async def test_altitude_kind(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 1500}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "altitude"})
        assert result == 1500

    @pytest.mark.asyncio
    async def test_distinct_countries_kind(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 5}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "distinct_countries"})
        assert result == 5

    @pytest.mark.asyncio
    async def test_distinct_countries_no_rows(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "distinct_countries"})
        assert result == 0

    @pytest.mark.asyncio
    async def test_dt_matrix_counts_covered_cells(self):
        from app.services.progress_aggregates import _aggregate_total

        rows = [{"_id": {"d": 1.0, "t": 1.0}}, {"_id": {"d": 2.5, "t": 3.0}}]
        coll = _mock_aggregate_coll(rows)
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "dt_matrix"})
        assert result == 2

    @pytest.mark.asyncio
    async def test_dt_matrix_skips_none_values(self):
        from app.services.progress_aggregates import _aggregate_total

        rows = [{"_id": {"d": None, "t": 1.0}}, {"_id": {"d": 1.5, "t": None}}]
        coll = _mock_aggregate_coll(rows)
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "dt_matrix"})
        assert result == 0

    @pytest.mark.asyncio
    async def test_list_condition_applied(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([{"total": 10}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(
                _UID,
                {"difficulty": [{"$gte": 1.0}, {"$lte": 3.0}]},
                {"kind": "difficulty"},
            )
        assert result == 10

    @pytest.mark.asyncio
    async def test_no_rows_returns_zero(self):
        from app.services.progress_aggregates import _aggregate_total

        coll = _mock_aggregate_coll([])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _aggregate_total(_UID, {}, {"kind": "difficulty"})
        assert result == 0


class TestNthFoundDate:
    @pytest.mark.asyncio
    async def test_n_zero_returns_none_without_db(self):
        from app.services.progress_aggregates import _nth_found_date

        # n <= 0 returns None before any DB call — no patch needed
        result = await _nth_found_date(_UID, {}, 0)
        assert result is None

    @pytest.mark.asyncio
    async def test_n_negative_returns_none_without_db(self):
        from app.services.progress_aggregates import _nth_found_date

        result = await _nth_found_date(_UID, {}, -3)
        assert result is None

    @pytest.mark.asyncio
    async def test_found_returns_date(self):
        from app.services.progress_aggregates import _nth_found_date

        d = date(2025, 6, 15)
        coll = _mock_aggregate_coll([{"found_date": d}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _nth_found_date(_UID, {}, 1)
        assert result == d

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        from app.services.progress_aggregates import _nth_found_date

        coll = _mock_aggregate_coll([])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _nth_found_date(_UID, {}, 3)
        assert result is None

    @pytest.mark.asyncio
    async def test_with_list_condition(self):
        from app.services.progress_aggregates import _nth_found_date

        d = date(2025, 3, 10)
        coll = _mock_aggregate_coll([{"found_date": d}])
        with patch("app.services.progress_aggregates.get_collection", return_value=coll):
            result = await _nth_found_date(_UID, {"difficulty": [{"$gte": 1.0}]}, 1)
        assert result == d


class TestFirstFoundDate:
    @pytest.mark.asyncio
    async def test_delegates_to_nth_with_n1(self):
        from app.services.progress_aggregates import _first_found_date

        d = date(2025, 1, 1)
        with patch(
            "app.services.progress_aggregates._nth_found_date", new=AsyncMock(return_value=d)
        ) as mock:
            result = await _first_found_date(_UID, {})

        mock.assert_awaited_once_with(_UID, {}, 1)
        assert result == d
