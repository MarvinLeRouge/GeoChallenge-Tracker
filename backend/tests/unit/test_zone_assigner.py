"""Unit tests for zone_assigner — 3-pass zone assignment pipeline.

All DB access and sub-services (zone_utils, zone_nominatim) are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.zones.zone_assigner import assign_zones_to_caches

# ── Factories ─────────────────────────────────────────────────────────────────


def _cache(gc: str, lat: float = 48.5, lon: float = 2.5) -> dict:
    return {"GC": gc, "lat": lat, "lon": lon}


def _cache_no_coords(gc: str) -> dict:
    return {"GC": gc}


def _zone(level1: str | None, level2: str | None) -> dict:
    return {"country": "FR", "level1": level1, "level2": level2}


def _spatial_index_stub():
    """Return a minimal SpatialIndex-like stub (NamedTuple fields not needed in mocks)."""
    return MagicMock()


# ── Patch helpers ─────────────────────────────────────────────────────────────


def _patch_get_index(idx1=None, idx2=None):
    """Patches _get_index to return idx1 for level=1, idx2 for level=2."""

    async def _get(country_code: str, level: int):
        return idx1 if level == 1 else idx2

    return patch("app.services.zones.zone_assigner._get_index", side_effect=_get)


def _patch_shapely(zone_map: dict):
    """Patches resolve_zones_for_point. zone_map: {gc_or_coords → zones_dict}."""
    call_count = [0]
    results = list(zone_map.values())

    def _resolve(lat, lon, country_code, idx1, idx2, *, exact_only=False):
        idx = call_count[0]
        call_count[0] += 1
        return results[idx] if idx < len(results) else _zone(None, None)

    return patch("app.services.zones.zone_assigner.resolve_zones_for_point", side_effect=_resolve)


def _patch_nominatim(results: list[dict]):
    return patch(
        "app.services.zones.zone_assigner.resolve_zones_batch",
        new=AsyncMock(return_value=results),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAssignZonesToCachesSkips:
    """Caches without coordinates or unavailable indexes are silently skipped."""

    @pytest.mark.asyncio
    async def test_skips_caches_without_coordinates(self):
        caches = [_cache_no_coords("GC01"), {"GC": "GC02", "lat": None, "lon": None}]
        idx = _spatial_index_stub()

        with _patch_get_index(idx, idx), _patch_shapely({}), _patch_nominatim([]):
            await assign_zones_to_caches(caches)

        assert "zones" not in caches[0]
        assert "zones" not in caches[1]

    @pytest.mark.asyncio
    async def test_skips_when_index_unavailable(self):
        caches = [_cache("GC01")]

        with _patch_get_index(None, None):
            await assign_zones_to_caches(caches)

        assert "zones" not in caches[0]

    @pytest.mark.asyncio
    async def test_skips_when_level1_index_none(self):
        caches = [_cache("GC01")]
        idx2 = _spatial_index_stub()

        with _patch_get_index(None, idx2):
            await assign_zones_to_caches(caches)

        assert "zones" not in caches[0]


class TestAssignZonesToCachesPass1:
    """Pass 1: Shapely exact match assigns zones directly."""

    @pytest.mark.asyncio
    async def test_all_matched_by_shapely(self):
        caches = [_cache("GC01"), _cache("GC02")]
        idx = _spatial_index_stub()
        zones = _zone("FR-84", "FR-38")

        with _patch_get_index(idx, idx), _patch_shapely({0: zones, 1: zones}), _patch_nominatim([]):
            await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == zones
        assert caches[1]["zones"] == zones

    @pytest.mark.asyncio
    async def test_partial_match_unmatched_sent_to_nominatim(self):
        """First cache matched by Shapely, second falls through to Nominatim."""
        caches = [_cache("GC01"), _cache("GC02")]
        idx = _spatial_index_stub()

        matched = _zone("FR-84", "FR-38")
        unmatched = _zone(None, None)  # will trigger pass 2

        nominatim_result = _zone("FR-93", "FR-83")

        call_count = [0]

        def _resolve(lat, lon, country_code, idx1, idx2, *, exact_only=False):
            current = call_count[0]
            call_count[0] += 1
            return matched if current == 0 else unmatched

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point", side_effect=_resolve
            ):
                with _patch_nominatim([nominatim_result]):
                    await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == matched
        assert caches[1]["zones"] == nominatim_result


class TestAssignZonesToCachesPass2:
    """Pass 2: Nominatim resolves points that Shapely missed."""

    @pytest.mark.asyncio
    async def test_nominatim_resolves_unmatched(self):
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()
        nominatim_result = _zone("FR-93", "FR-83")

        unmatched = _zone(None, None)

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point",
                return_value=unmatched,
            ):
                with _patch_nominatim([nominatim_result]):
                    await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == nominatim_result

    @pytest.mark.asyncio
    async def test_nominatim_partial_fallback_to_pass3(self):
        """Nominatim resolves level2=None → cache goes to pass 3 (nearest polygon)."""
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()
        unmatched = _zone(None, None)
        nominatim_no_dept = _zone("FR-93", None)  # level2 is None → pass 3
        pass3_result = _zone("FR-93", "FR-83")

        call_count = [0]

        def _resolve(lat, lon, country_code, idx1, idx2, *, exact_only=False):
            call_count[0] += 1
            if exact_only:
                return unmatched
            return pass3_result  # pass 3 call (exact_only=False)

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point", side_effect=_resolve
            ):
                with _patch_nominatim([nominatim_no_dept]):
                    await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == pass3_result


class TestAssignZonesToCachesPass3:
    """Pass 3: Nearest-polygon fallback for points still unresolved after Nominatim."""

    @pytest.mark.asyncio
    async def test_pass3_nearest_fallback_applied(self):
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()
        pass3_result = _zone("FR-93", "FR-83")

        call_count = [0]

        def _resolve(lat, lon, country_code, idx1, idx2, *, exact_only=False):
            call_count[0] += 1
            if exact_only:
                return _zone(None, None)
            return pass3_result

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point", side_effect=_resolve
            ):
                with _patch_nominatim([_zone(None, None)]):
                    await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == pass3_result

    @pytest.mark.asyncio
    async def test_pass3_exception_does_not_raise(self):
        """An exception in pass 3 is caught and the cache is left without zones."""
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()

        call_count = [0]

        def _resolve(lat, lon, country_code, idx1, idx2, *, exact_only=False):
            call_count[0] += 1
            if exact_only:
                return _zone(None, None)
            raise RuntimeError("geometry error")

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point", side_effect=_resolve
            ):
                with _patch_nominatim([_zone(None, None)]):
                    await assign_zones_to_caches(caches)  # must not raise

        assert "zones" not in caches[0]
