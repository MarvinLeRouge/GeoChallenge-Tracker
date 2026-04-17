"""Unit tests for zone_assigner — 3-pass zone assignment pipeline.

All DB access and sub-services (zone_utils, zone_nominatim) are mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.zones.zone_assigner import _get_index, _index_cache, assign_zones_to_caches

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


class TestAssignZonesToCachesPass1Exception:
    """Pass 1 exception is caught and cache is forwarded to Nominatim (Pass 2)."""

    @pytest.mark.asyncio
    async def test_shapely_exception_in_pass1_sends_to_nominatim(self):
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()
        nominatim_result = _zone("FR-84", "FR-38")

        def _raise_on_exact(lat, lon, country_code, idx1, idx2, *, exact_only=False):
            if exact_only:
                raise RuntimeError("geometry error")
            return nominatim_result

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point",
                side_effect=_raise_on_exact,
            ):
                with _patch_nominatim([nominatim_result]):
                    await assign_zones_to_caches(caches)

        assert caches[0]["zones"] == nominatim_result


class TestAssignZonesToCachesForeignFlag:
    """Foreign caches (is_foreign=True) are not sent to Pass 3."""

    @pytest.mark.asyncio
    async def test_foreign_cache_skipped_in_pass3(self):
        caches = [_cache("GC01")]
        idx = _spatial_index_stub()
        foreign_result = {"country": "ES", "level1": None, "level2": None, "_foreign": True}

        with _patch_get_index(idx, idx):
            with patch(
                "app.services.zones.zone_assigner.resolve_zones_for_point",
                return_value=_zone(None, None),
            ):
                with _patch_nominatim([foreign_result]):
                    await assign_zones_to_caches(caches)

        assert "zones" not in caches[0]


# ── _get_index ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_index_cache():
    _index_cache.clear()
    yield
    _index_cache.clear()


class TestGetIndex:
    @pytest.mark.asyncio
    async def test_returns_cached_index_on_second_call(self):
        mock_index = _spatial_index_stub()
        _index_cache[("FR", 1)] = mock_index

        result = await _get_index("FR", 1)

        assert result is mock_index

    @pytest.mark.asyncio
    async def test_returns_none_when_geojson_file_missing(self, tmp_path):
        mock_col = MagicMock()
        mock_col.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "geojson_file": "FR/regions.geojson",
                    "country_code": "FR",
                    "level": 1,
                    "code": "FR-84",
                }
            ]
        )

        async def _get_col(name):
            return mock_col

        with patch("app.services.zones.zone_assigner.get_collection", side_effect=_get_col):
            with patch("app.services.zones.zone_assigner.get_settings") as mock_settings:
                mock_settings.return_value.geo_data_dir = str(tmp_path)
                # File intentionally not created → geojson_path.exists() is False
                result = await _get_index("FR", 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_builds_and_caches_index_when_geojson_exists(self, tmp_path):
        fr_dir = tmp_path / "FR"
        fr_dir.mkdir()
        geojson_path = fr_dir / "regions.geojson"
        geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

        zone_docs = [
            {
                "geojson_file": "FR/regions.geojson",
                "country_code": "FR",
                "level": 1,
                "code": "FR-84",
            }
        ]
        mock_col = MagicMock()
        mock_col.find.return_value.to_list = AsyncMock(return_value=zone_docs)

        async def _get_col(name):
            return mock_col

        mock_index = _spatial_index_stub()
        mock_index.shapes = []

        with patch("app.services.zones.zone_assigner.get_collection", side_effect=_get_col):
            with patch("app.services.zones.zone_assigner.get_settings") as mock_settings:
                mock_settings.return_value.geo_data_dir = str(tmp_path)
                with patch(
                    "app.services.zones.zone_assigner.build_spatial_index",
                    return_value=mock_index,
                ) as mock_build:
                    result = await _get_index("FR", 1)

        assert result is mock_index
        assert ("FR", 1) in _index_cache
        mock_build.assert_called_once()
