# backend/app/api/dto/geo_admin.py
# Input/output DTOs for the /admin/geo endpoints.

from __future__ import annotations

from pydantic import BaseModel


class MissingCountryItem(BaseModel):
    """A country with found caches but no GeoJSON coverage on disk yet.

    Attributes:
        code (str): ISO country code, e.g. "DE".
        found_count (int): Number of found-cache records in this country, across all users.
    """

    code: str
    found_count: int


class MissingCountriesResponse(BaseModel):
    """Response for GET /admin/geo/missing-countries.

    Attributes:
        items (list[MissingCountryItem]): Missing countries, sorted by found_count desc.
    """

    items: list[MissingCountryItem]


class GeoUploadResponse(BaseModel):
    """Response for POST /admin/geo/{country_code}/upload.

    Attributes:
        country_code (str): ISO country code the file was uploaded for.
        level (int): Administrative level (0, 1 or 2).
        features_count (int): Number of features in the uploaded FeatureCollection.
        inserted (int): Number of new administrative_zones documents created (0 at level 0).
        updated (int): Number of existing administrative_zones documents updated (0 at level 0).
    """

    country_code: str
    level: int
    features_count: int
    inserted: int
    updated: int
