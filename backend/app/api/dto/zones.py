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


class CacheInZone(BaseModel):
    """Compact cache summary for use inside a zone detail popover.

    Attributes:
        GC (str): Geocaching code.
        title (str): Cache title.
        type_code (str | None): Cache type code (e.g. "traditional").
        difficulty (float | None): Difficulty rating.
        terrain (float | None): Terrain rating.
    """

    GC: str
    title: str
    type_code: str | None = None
    difficulty: float | None = None
    terrain: float | None = None


class ZoneDetail(BaseModel):
    """Detail of an administrative zone with its top caches.

    Attributes:
        code (str): Zone code.
        name (str): Display name.
        cache_count (int): Total number of user caches in this zone.
        caches (list[CacheInZone]): First 10 caches (for popover preview).
    """

    code: str
    name: str
    cache_count: int
    caches: list[CacheInZone]
