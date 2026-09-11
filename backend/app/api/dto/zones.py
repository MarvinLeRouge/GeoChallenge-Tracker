# backend/app/api/dto/zones.py
# Input/output DTOs for the /api/zones endpoints.

from __future__ import annotations

from pydantic import BaseModel


class ZoneListItem(BaseModel):
    """Summary of an administrative zone with its cache count.

    Attributes:
        code (str): Zone code, e.g. "FR-84".
        name (str): Display name, e.g. "Auvergne-Rhône-Alpes".
        cache_count (int): Number of user caches in this zone.
    """

    code: str
    name: str
    cache_count: int


class ZoneListResponse(BaseModel):
    """Response for GET /api/zones.

    Attributes:
        items (list[ZoneListItem]): Zones with cache counts, sorted by name.
    """

    items: list[ZoneListItem]


class ZoneTypeStatItem(BaseModel):
    """Count of found caches for a single cache type within a zone.

    Attributes:
        type_code (str): Cache type code, e.g. "traditional".
        type_name (str): Display name, e.g. "Traditional".
        count (int): Number of found caches of this type in the zone (0 if none).
    """

    type_code: str
    type_name: str
    count: int


class ZoneDetail(BaseModel):
    """Detail of an administrative zone with its per-type cache breakdown.

    Attributes:
        code (str): Zone code.
        name (str): Display name.
        cache_count (int): Total number of user caches in this zone (sum of type_counts).
        type_counts (list[ZoneTypeStatItem]): All cache types ordered by canonical GC order,
            count is 0 for types with no found caches in this zone.
    """

    code: str
    name: str
    cache_count: int
    type_counts: list[ZoneTypeStatItem]
