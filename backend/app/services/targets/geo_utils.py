# backend/app/services/targets/geo_utils.py
# Geographic utilities for distance calculation and geo filters.

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from bson import ObjectId

from app.db.mongodb import get_collection


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the haversine distance between two points.

    Args:
        lat1: Latitude of the first point.
        lon1: Longitude of the first point.
        lat2: Latitude of the second point.
        lon2: Longitude of the second point.

    Returns:
        float: Distance in kilometers.
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Earth radius in km
    r = 6371
    return c * r


async def get_user_location(user_id: ObjectId) -> tuple[float, float] | None:
    """Retrieve a user's location.

    Args:
        user_id: User identifier.

    Returns:
        tuple[float, float] | None: (latitude, longitude) or None if no location is saved.
    """
    coll_users = await get_collection("users")
    user_doc = await coll_users.find_one({"_id": user_id}, {"location": 1})

    if not user_doc or not user_doc.get("location"):
        return None

    location = user_doc["location"]
    if location.get("type") != "Point":
        return None

    coordinates = location.get("coordinates", [])
    if len(coordinates) != 2:
        return None

    lon, lat = coordinates  # GeoJSON format: [longitude, latitude]
    return lat, lon


def build_geo_pipeline_stage(lat: float, lon: float, radius_km: float) -> dict[str, Any]:
    """Build a MongoDB pipeline stage for a geographic filter.

    Args:
        lat: Center latitude.
        lon: Center longitude.
        radius_km: Radius in kilometers.

    Returns:
        dict: $geoNear stage for the aggregation pipeline.
    """
    return {
        "$geoNear": {
            "near": {"type": "Point", "coordinates": [lon, lat]},
            "distanceField": "distance_m",
            "maxDistance": radius_km * 1000,  # MongoDB uses meters
            "spherical": True,
        }
    }


def calculate_geo_score(distance_m: float, radius_km: float) -> float:
    """Calculate a geographic score based on distance.

    Description:
        Smoothed score that decreases with distance using a sigmoidal
        function to avoid discontinuities.

    Args:
        distance_m: Distance in meters.
        radius_km: Reference radius in kilometers.

    Returns:
        float: Score between 0 and 1.
    """
    if distance_m <= 0:
        return 1.0

    # Smoothed function based on relative distance:
    # Score = 1 / (1 + (distance / (radius * 0.3))^2)
    # Yields ~0.9 at radius/3, ~0.5 at radius, ~0.1 at 2*radius
    relative_distance = distance_m / (radius_km * 300)  # 300m = 0.3km factor
    return 1.0 / (1.0 + relative_distance**2)
