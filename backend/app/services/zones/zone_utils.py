# backend/app/services/zones/zone_utils.py
# Spatial utilities for assigning administrative zones to cache coordinates.
# Uses Shapely STRtree for fast point-in-polygon queries with a nearest-zone fallback
# to handle boundary approximation issues (coastal / border caches).

from __future__ import annotations

import json
import logging
from functools import cache
from pathlib import Path
from typing import NamedTuple

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

log = logging.getLogger(__name__)

# Maximum distance (degrees) to assign the nearest zone when no polygon contains the point.
# ~10 km at mid-latitudes. Caches beyond this threshold are stored with zones.levelN = None.
FALLBACK_MAX_DISTANCE_DEG: float = 0.1


class SpatialIndex(NamedTuple):
    """Prebuilt spatial index for one administrative level.

    Attributes:
        tree (STRtree): Shapely STRtree built from zone geometries.
        shapes (list): Ordered list of Shapely geometries (same order as zones).
        zones (list[dict]): Zone documents in the same order as shapes.
    """

    tree: STRtree
    shapes: list
    zones: list[dict]


@cache
def _load_feature_collection(geojson_path: str) -> list[dict]:
    """Loads and caches a GeoJSON FeatureCollection from disk.

    Args:
        geojson_path (str): Absolute path to the FeatureCollection file.

    Returns:
        list[dict]: List of GeoJSON features.
    """
    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)
    return fc.get("features", [])


def build_spatial_index(geojson_path: Path, zone_docs: list[dict]) -> SpatialIndex:
    """Builds a STRtree spatial index from a GeoJSON FeatureCollection.

    Description:
        Loads the FeatureCollection, matches features to zone documents by
        `feature_code`, and constructs an STRtree for fast spatial queries.

    Args:
        geojson_path (Path): Path to the FeatureCollection GeoJSON file.
        zone_docs (list[dict]): Zone documents from `administrative_zones`
            collection (must include `feature_code`).

    Returns:
        SpatialIndex: Populated index (tree, shapes, zones).
    """
    features = _load_feature_collection(str(geojson_path))
    code_to_geom = {str(f["properties"]["code"]): shape(f["geometry"]) for f in features}

    shapes = []
    matched_zones = []
    for zone in zone_docs:
        geom = code_to_geom.get(zone["feature_code"])
        if geom is None:
            log.warning(
                "No geometry found for zone %s (feature_code=%s)",
                zone["code"],
                zone["feature_code"],
            )
            continue
        shapes.append(geom)
        matched_zones.append(zone)

    tree = STRtree(shapes)
    return SpatialIndex(tree=tree, shapes=shapes, zones=matched_zones)


def find_zone_for_point(
    lat: float,
    lon: float,
    index: SpatialIndex,
    *,
    exact_only: bool = False,
    fallback_max_distance: float = FALLBACK_MAX_DISTANCE_DEG,
) -> dict | None:
    """Finds the administrative zone containing (or nearest to) a point.

    Description:
        Two-pass algorithm:
        1. Exact point-in-polygon via STRtree candidates.
        2. If no match and `exact_only=False`: nearest zone by polygon distance,
           within `fallback_max_distance`. Used as last resort when Nominatim
           is unavailable or returns no result.

    Args:
        lat (float): Latitude (decimal degrees).
        lon (float): Longitude (decimal degrees).
        index (SpatialIndex): Prebuilt spatial index for the target level.
        exact_only (bool): If True, return None immediately when no polygon contains
            the point (disables the nearest-zone fallback).
        fallback_max_distance (float): Maximum distance (degrees) for the nearest-zone fallback.

    Returns:
        dict | None: Zone document if found, None otherwise.
    """
    point = Point(lon, lat)

    # Pass 1: exact containment via STRtree candidates (bbox pre-filter + precise check)
    candidate_indices = index.tree.query(point)
    for idx in candidate_indices:
        if index.shapes[idx].contains(point):
            return index.zones[idx]

    if exact_only:
        return None

    # Pass 2: nearest zone fallback (last resort — boundary/coastal approximation issues)
    if not index.shapes:
        return None

    min_dist = float("inf")
    nearest_zone = None
    for geom, zone in zip(index.shapes, index.zones):
        dist = geom.distance(point)
        if dist < min_dist:
            min_dist = dist
            nearest_zone = zone

    if min_dist <= fallback_max_distance:
        log.debug(
            "Zone %s assigned via nearest-polygon fallback (dist=%.5f°) for point (%.5f, %.5f)",
            nearest_zone["code"] if nearest_zone else None,
            min_dist,
            lat,
            lon,
        )
        return nearest_zone

    return None


def resolve_zones_for_point(
    lat: float,
    lon: float,
    country_code: str,
    level1_index: SpatialIndex,
    level2_index: SpatialIndex,
    *,
    exact_only: bool = False,
) -> dict[str, str | None]:
    """Resolves full zone hierarchy for a geographic point.

    Description:
        Finds level1 (region) and level2 (department) zones for a given coordinate.
        Returns a dict suitable for storing in `cache.zones`.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        country_code (str): ISO country code (e.g. "FR").
        level1_index (SpatialIndex): Spatial index for level 1 zones.
        level2_index (SpatialIndex): Spatial index for level 2 zones.
        exact_only (bool): If True, disable the nearest-polygon fallback.

    Returns:
        dict[str, str | None]: Zone assignment, e.g.
            {"country": "FR", "level1": "FR-84", "level2": "FR-38"}
    """
    level1_zone = find_zone_for_point(lat, lon, level1_index, exact_only=exact_only)
    level2_zone = find_zone_for_point(lat, lon, level2_index, exact_only=exact_only)

    return {
        "country": country_code,
        "level1": level1_zone["code"] if level1_zone else None,
        "level2": level2_zone["code"] if level2_zone else None,
    }
