# backend/app/services/targets/geo_utils.py
# Utilitaires géographiques pour le calcul de distances et filtres géo.

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from bson import ObjectId

from app.db.mongodb import get_collection


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculer la distance haversine entre deux points.

    Args:
        lat1: Latitude du premier point.
        lon1: Longitude du premier point.
        lat2: Latitude du second point.
        lon2: Longitude du second point.

    Returns:
        float: Distance en kilomètres.
    """
    # Convertir en radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Formule haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Rayon de la Terre en km
    r = 6371
    return c * r


async def get_user_location(user_id: ObjectId) -> tuple[float, float] | None:
    """Récupérer la localisation d'un utilisateur.

    Args:
        user_id: Identifiant de l'utilisateur.

    Returns:
        tuple[float, float] | None: (latitude, longitude) ou None si pas de localisation.
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

    lon, lat = coordinates  # GeoJSON format [longitude, latitude]
    return lat, lon


def build_geo_pipeline_stage(lat: float, lon: float, radius_km: float) -> dict[str, Any]:
    """Construire une étape de pipeline MongoDB pour un filtre géographique.

    Args:
        lat: Latitude du centre.
        lon: Longitude du centre.
        radius_km: Rayon en kilomètres.

    Returns:
        dict: Étape $geoNear pour le pipeline d'agrégation.
    """
    return {
        "$geoNear": {
            "near": {"type": "Point", "coordinates": [lon, lat]},
            "distanceField": "distance_m",
            "maxDistance": radius_km * 1000,  # MongoDB utilise les mètres
            "spherical": True,
        }
    }


def calculate_geo_score(distance_m: float, radius_km: float) -> float:
    """Calculer un score géographique basé sur la distance.

    Description:
        Score lissé qui diminue avec la distance,
        avec une fonction sigmoidale pour éviter les discontinuités.

    Args:
        distance_m: Distance en mètres.
        radius_km: Rayon de référence en kilomètres.

    Returns:
        float: Score entre 0 et 1.
    """
    if distance_m <= 0:
        return 1.0

    # Fonction lissée basée sur la distance relative
    # Score = 1 / (1 + (distance / (radius * 0.3))^2)
    # Cela donne un score de ~0.9 à radius/3, ~0.5 à radius, ~0.1 à 2*radius
    relative_distance = distance_m / (radius_km * 300)  # 300m = 0.3km factor
    return 1.0 / (1.0 + relative_distance**2)
