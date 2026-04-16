"""Unit tests for zone_utils — Shapely STRtree point-in-polygon logic.

No database or file I/O required: all spatial data is built in-memory.
"""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import box as shapely_box
from shapely.geometry import mapping
from shapely.strtree import STRtree

from app.services.zones.zone_utils import (
    SpatialIndex,
    build_spatial_index,
    find_zone_for_point,
    resolve_zones_for_point,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_index(boxes: list[tuple[float, float, float, float]], codes: list[str]) -> SpatialIndex:
    """Build a SpatialIndex directly from bounding boxes (no file I/O)."""
    shapes = [shapely_box(*b) for b in boxes]
    zones = [{"code": c, "feature_code": c.split("-")[-1]} for c in codes]
    tree = STRtree(shapes)
    return SpatialIndex(tree=tree, shapes=shapes, zones=zones)


def _write_geojson(features: list[dict], tmp_dir: Path) -> Path:
    """Write a minimal FeatureCollection GeoJSON to a temp file."""
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_dir / "test.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")
    return path


# ── Tests: find_zone_for_point ─────────────────────────────────────────────


class TestFindZoneForPoint:
    """Tests for find_zone_for_point."""

    def _index(self) -> SpatialIndex:
        """Two adjacent rectangles: zone A covers lon 0-1 / lat 0-1, zone B covers 1-2 / 0-1."""
        # shapely_box(minx, miny, maxx, maxy) → (lon_min, lat_min, lon_max, lat_max)
        return _make_index(
            [(0.0, 0.0, 1.0, 1.0), (1.0, 0.0, 2.0, 1.0)],
            ["FR-A", "FR-B"],
        )

    def test_point_inside_first_zone(self):
        idx = self._index()
        result = find_zone_for_point(0.5, 0.5, idx)
        assert result is not None
        assert result["code"] == "FR-A"

    def test_point_inside_second_zone(self):
        idx = self._index()
        result = find_zone_for_point(0.5, 1.5, idx)
        assert result is not None
        assert result["code"] == "FR-B"

    def test_point_outside_all_zones_exact_only(self):
        idx = self._index()
        # Point well outside both polygons
        result = find_zone_for_point(5.0, 5.0, idx, exact_only=True)
        assert result is None

    def test_point_outside_within_fallback_distance(self):
        idx = self._index()
        # Point at (0.5, -0.05) — just below zone A (lat -0.05), within 0.1° fallback
        result = find_zone_for_point(-0.05, 0.5, idx, exact_only=False, fallback_max_distance=0.1)
        assert result is not None
        assert result["code"] == "FR-A"

    def test_point_outside_beyond_fallback_distance(self):
        idx = self._index()
        # Point at lat=-5, lon=0.5 — 5° below zone A, beyond 0.1° threshold
        result = find_zone_for_point(-5.0, 0.5, idx, exact_only=False, fallback_max_distance=0.1)
        assert result is None

    def test_exact_only_disables_fallback(self):
        idx = self._index()
        # Close to zone A boundary but outside
        result = find_zone_for_point(-0.05, 0.5, idx, exact_only=True)
        assert result is None

    def test_empty_index_returns_none(self):
        idx = SpatialIndex(tree=STRtree([]), shapes=[], zones=[])
        result = find_zone_for_point(0.5, 0.5, idx)
        assert result is None


# ── Tests: resolve_zones_for_point ────────────────────────────────────────


class TestResolveZonesForPoint:
    """Tests for resolve_zones_for_point."""

    def _indexes(self):
        """Level 1: one large box (FR-84). Level 2: same box split into two (FR-07, FR-26)."""
        idx1 = _make_index([(0.0, 0.0, 4.0, 4.0)], ["FR-84"])
        idx2 = _make_index(
            [(0.0, 0.0, 2.0, 4.0), (2.0, 0.0, 4.0, 4.0)],
            ["FR-07", "FR-26"],
        )
        return idx1, idx2

    def test_point_matched_at_both_levels(self):
        idx1, idx2 = self._indexes()
        result = resolve_zones_for_point(2.0, 1.0, "FR", idx1, idx2)
        assert result["country"] == "FR"
        assert result["level1"] == "FR-84"
        assert result["level2"] == "FR-07"

    def test_point_outside_all_zones_exact(self):
        idx1, idx2 = self._indexes()
        result = resolve_zones_for_point(10.0, 10.0, "FR", idx1, idx2, exact_only=True)
        assert result["level1"] is None
        assert result["level2"] is None

    def test_country_code_propagated(self):
        idx1, idx2 = self._indexes()
        result = resolve_zones_for_point(2.0, 1.0, "FR", idx1, idx2)
        assert result["country"] == "FR"


# ── Tests: build_spatial_index ────────────────────────────────────────────


class TestBuildSpatialIndex:
    """Tests for build_spatial_index using a real GeoJSON file."""

    def test_build_index_from_geojson(self, tmp_path):
        # Build a minimal FeatureCollection with two zone features
        zone_a_geom = mapping(shapely_box(0.0, 0.0, 1.0, 1.0))
        zone_b_geom = mapping(shapely_box(1.0, 0.0, 2.0, 1.0))
        features = [
            {"type": "Feature", "properties": {"code": "A1"}, "geometry": zone_a_geom},
            {"type": "Feature", "properties": {"code": "B1"}, "geometry": zone_b_geom},
        ]
        geojson_path = _write_geojson(features, tmp_path)

        zone_docs = [
            {"code": "FR-A1", "feature_code": "A1"},
            {"code": "FR-B1", "feature_code": "B1"},
        ]
        idx = build_spatial_index(geojson_path, zone_docs)

        assert len(idx.shapes) == 2
        assert len(idx.zones) == 2

    def test_build_index_skips_missing_feature_code(self, tmp_path):
        zone_a_geom = mapping(shapely_box(0.0, 0.0, 1.0, 1.0))
        features = [
            {"type": "Feature", "properties": {"code": "A1"}, "geometry": zone_a_geom},
        ]
        geojson_path = _write_geojson(features, tmp_path)

        zone_docs = [
            {"code": "FR-A1", "feature_code": "A1"},
            {"code": "FR-MISSING", "feature_code": "NOTEXIST"},  # no matching feature
        ]
        idx = build_spatial_index(geojson_path, zone_docs)

        assert len(idx.shapes) == 1
        assert idx.zones[0]["code"] == "FR-A1"

    def test_built_index_correctly_locates_point(self, tmp_path):
        zone_a_geom = mapping(shapely_box(0.0, 0.0, 1.0, 1.0))
        features = [
            {"type": "Feature", "properties": {"code": "38"}, "geometry": zone_a_geom},
        ]
        geojson_path = _write_geojson(features, tmp_path)
        zone_docs = [{"code": "FR-38", "feature_code": "38"}]

        idx = build_spatial_index(geojson_path, zone_docs)
        result = find_zone_for_point(0.5, 0.5, idx)

        assert result is not None
        assert result["code"] == "FR-38"
