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
