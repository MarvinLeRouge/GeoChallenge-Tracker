"""Unit tests for app/services/zones/zone_service.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.zones.zone_service import (
    get_zone_detail,
    get_zones_with_counts,
)

USER_ID = ObjectId()
TYPE_OID = ObjectId()


# ── Factories ──────────────────────────────────────────────────────────────────


def _agg_cursor(results: list) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=results)
    return cursor


def _find_cursor(results: list) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=results)
    return cursor


def _found_col(*agg_result_sets: list) -> MagicMock:
    """Build a found_caches mock where each aggregate() call returns the next result set."""
    col = MagicMock()
    col.aggregate = MagicMock(side_effect=[_agg_cursor(r) for r in agg_result_sets])
    return col


def _zones_col(
    find_one_side_effect: list | None = None,
    find_results: list | None = None,
) -> MagicMock:
    col = MagicMock()
    if find_one_side_effect is not None:
        col.find_one = AsyncMock(side_effect=find_one_side_effect)
    else:
        col.find_one = AsyncMock(return_value=None)
    col.find = MagicMock(return_value=_find_cursor(find_results or []))
    return col


def _types_col(doc: dict | None = None, all_docs: list | None = None) -> MagicMock:
    col = MagicMock()
    col.find_one = AsyncMock(return_value=doc)
    col.find = MagicMock(return_value=_find_cursor(all_docs or []))
    return col


def _countries_col(find_results: list | None = None) -> MagicMock:
    col = MagicMock()
    col.find = MagicMock(return_value=_find_cursor(find_results or []))
    return col


def _patch_get_collection(found, zones, types=None, countries=None):
    types = types or _types_col()
    countries = countries or _countries_col()

    async def _get(name: str):
        if name == "found_caches":
            return found
        if name == "administrative_zones":
            return zones
        if name == "cache_types":
            return types
        if name == "countries":
            return countries
        raise AssertionError(f"Unexpected collection: {name}")

    return patch("app.services.zones.zone_service.get_collection", side_effect=_get)


# ── get_zones_with_counts ──────────────────────────────────────────────────────


class TestGetZonesWithCounts:
    @pytest.mark.asyncio
    async def test_returns_empty_when_type_codes_unknown(self):
        found = _found_col()
        zones = _zones_col()
        types = _types_col(all_docs=[])

        with _patch_get_collection(found, zones, types):
            result = await get_zones_with_counts(1, USER_ID, country="FR", type_codes=["unknown"])

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_found_caches(self):
        found = _found_col([])
        zones = _zones_col()

        with _patch_get_collection(found, zones):
            result = await get_zones_with_counts(1, USER_ID, country="FR")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_items_sorted_by_name(self):
        found = _found_col(
            [
                {"_id": "FR-84", "cache_count": 10},
                {"_id": "FR-93", "cache_count": 5},
            ]
        )
        zones = _zones_col(
            find_results=[
                {"code": "FR-84", "name": "Provence-Alpes-Côte d'Azur", "level": 1},
                {"code": "FR-93", "name": "Auvergne-Rhône-Alpes", "level": 1},
            ]
        )

        with _patch_get_collection(found, zones):
            result = await get_zones_with_counts(1, USER_ID, country="FR")

        assert len(result) == 2
        assert result[0].name == "Auvergne-Rhône-Alpes"
        assert result[0].cache_count == 5
        assert result[1].name == "Provence-Alpes-Côte d'Azur"
        assert result[1].cache_count == 10

    @pytest.mark.asyncio
    async def test_applies_type_filter_in_pipeline(self):
        found = _found_col([])
        zones = _zones_col()
        types = _types_col(all_docs=[{"_id": TYPE_OID, "code": "traditional"}])

        with _patch_get_collection(found, zones, types):
            await get_zones_with_counts(1, USER_ID, country="FR", type_codes=["traditional"])

        pipeline = found.aggregate.call_args[0][0]
        match_stages = [
            s["$match"]
            for s in pipeline
            if "$match" in s and "cache.type_id" in s.get("$match", {})
        ]
        assert len(match_stages) == 1
        assert match_stages[0]["cache.type_id"] == {"$in": [TYPE_OID]}

    @pytest.mark.asyncio
    async def test_applies_multiple_type_codes_via_in(self):
        found = _found_col([])
        zones = _zones_col()
        type_a, type_b = ObjectId(), ObjectId()
        types = _types_col(
            all_docs=[
                {"_id": type_a, "code": "traditional"},
                {"_id": type_b, "code": "mystery"},
            ]
        )

        with _patch_get_collection(found, zones, types):
            await get_zones_with_counts(
                1, USER_ID, country="FR", type_codes=["traditional", "mystery"]
            )

        pipeline = found.aggregate.call_args[0][0]
        match_stage = next(
            s["$match"]
            for s in pipeline
            if "$match" in s and "cache.type_id" in s.get("$match", {})
        )
        assert set(match_stage["cache.type_id"]["$in"]) == {type_a, type_b}

    @pytest.mark.asyncio
    async def test_level0_groups_by_country_ignoring_country_param(self):
        found = _found_col(
            [
                {"_id": "FR", "cache_count": 10},
                {"_id": "DE", "cache_count": 2},
            ]
        )
        zones = _zones_col()
        countries = _countries_col(
            find_results=[
                {"code": "FR", "name": "France", "name_fr": "France"},
                {"code": "DE", "name": "Germany", "name_fr": "Allemagne"},
            ]
        )

        with _patch_get_collection(found, zones, countries=countries):
            result = await get_zones_with_counts(0, USER_ID)

        assert len(result) == 2
        assert result[0].code == "DE"
        assert result[1].code == "FR"
        pipeline = found.aggregate.call_args[0][0]
        group_stage = next(s["$group"] for s in pipeline if "$group" in s)
        assert group_stage["_id"] == "$cache.zones.country"

    @pytest.mark.asyncio
    async def test_level0_uses_name_fr_for_display(self):
        found = _found_col([{"_id": "DE", "cache_count": 1}])
        zones = _zones_col()
        countries = _countries_col(
            find_results=[{"code": "DE", "name": "Germany", "name_fr": "Allemagne"}]
        )

        with _patch_get_collection(found, zones, countries=countries):
            result = await get_zones_with_counts(0, USER_ID)

        assert result[0].name == "Allemagne"

    @pytest.mark.asyncio
    async def test_level0_falls_back_to_name_when_name_fr_missing(self):
        found = _found_col([{"_id": "DE", "cache_count": 1}])
        zones = _zones_col()
        countries = _countries_col(find_results=[{"code": "DE", "name": "Germany"}])

        with _patch_get_collection(found, zones, countries=countries):
            result = await get_zones_with_counts(0, USER_ID)

        assert result[0].name == "Germany"

    @pytest.mark.asyncio
    async def test_level0_drops_countries_with_no_reference_doc(self):
        found = _found_col([{"_id": "XX", "cache_count": 1}])
        zones = _zones_col()
        countries = _countries_col(find_results=[])

        with _patch_get_collection(found, zones, countries=countries):
            result = await get_zones_with_counts(0, USER_ID)

        assert result == []


# ── get_zone_detail ────────────────────────────────────────────────────────────


TYPE_A_OID = ObjectId()
TYPE_B_OID = ObjectId()

_ALL_TYPES = [
    {"_id": TYPE_A_OID, "code": "traditional", "name": "Traditional", "sort_order": 1},
    {"_id": TYPE_B_OID, "code": "mystery", "name": "Mystery", "sort_order": 2},
]


class TestGetZoneDetail:
    @pytest.mark.asyncio
    async def test_returns_none_when_zone_not_found(self):
        found = _found_col()
        zones = _zones_col(find_one_side_effect=[None, None])

        with _patch_get_collection(found, zones):
            result = await get_zone_detail("FR-UNKNOWN", USER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_level_hint_in_query(self):
        zone_doc = {"code": "FR-84", "name": "PACA", "level": 1}
        found = _found_col([])
        zones = _zones_col(find_one_side_effect=[zone_doc])
        types = _types_col(all_docs=_ALL_TYPES)

        with _patch_get_collection(found, zones, types):
            result = await get_zone_detail("FR-84", USER_ID, level=1)

        assert result is not None
        # Only one find_one call (the level-hint path)
        assert zones.find_one.call_count == 1
        zones.find_one.assert_called_once_with({"code": "FR-84", "level": 1})

    @pytest.mark.asyncio
    async def test_fallback_tries_level2_then_level1_when_no_hint(self):
        zone_doc = {"code": "FR-84", "name": "PACA", "level": 1}
        found = _found_col([])
        # First call (level 2) returns None, second call (level 1) returns zone
        zones = _zones_col(find_one_side_effect=[None, zone_doc])
        types = _types_col(all_docs=_ALL_TYPES)

        with _patch_get_collection(found, zones, types):
            result = await get_zone_detail("FR-84", USER_ID)

        assert result is not None
        assert result.name == "PACA"
        assert zones.find_one.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_all_types_including_zeros(self):
        zone_doc = {"code": "FR-84", "name": "PACA", "level": 1}
        found = _found_col([{"_id": TYPE_A_OID, "count": 3}])
        zones = _zones_col(find_one_side_effect=[zone_doc])
        types = _types_col(all_docs=_ALL_TYPES)

        with _patch_get_collection(found, zones, types):
            result = await get_zone_detail("FR-84", USER_ID, level=1)

        assert result is not None
        assert len(result.type_counts) == 2
        trad = next(t for t in result.type_counts if t.type_code == "traditional")
        mystery = next(t for t in result.type_counts if t.type_code == "mystery")
        assert trad.count == 3
        assert mystery.count == 0

    @pytest.mark.asyncio
    async def test_cache_count_is_sum_of_type_counts(self):
        zone_doc = {"code": "FR-38", "name": "Isère", "level": 2}
        found = _found_col([{"_id": TYPE_A_OID, "count": 3}, {"_id": TYPE_B_OID, "count": 2}])
        zones = _zones_col(find_one_side_effect=[zone_doc])
        types = _types_col(all_docs=_ALL_TYPES)

        with _patch_get_collection(found, zones, types):
            result = await get_zone_detail("FR-38", USER_ID, level=2)

        assert result is not None
        assert result.code == "FR-38"
        assert result.name == "Isère"
        assert result.cache_count == 5

    @pytest.mark.asyncio
    async def test_preserves_canonical_order(self):
        zone_doc = {"code": "FR-84", "name": "PACA", "level": 1}
        found = _found_col([])
        zones = _zones_col(find_one_side_effect=[zone_doc])
        # Provide types in reverse order to confirm sorting is applied
        reversed_types = list(reversed(_ALL_TYPES))
        types = _types_col(all_docs=reversed_types)

        with _patch_get_collection(found, zones, types):
            result = await get_zone_detail("FR-84", USER_ID, level=1)

        assert result is not None
        assert result.type_counts[0].type_code == "traditional"  # cache_type_id=2 first
        assert result.type_counts[1].type_code == "mystery"  # cache_type_id=8 second
