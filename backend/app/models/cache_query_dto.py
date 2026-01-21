from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class Range(BaseModel):
    """Range for numeric filters (e.g., difficulty, terrain)."""

    min: float | None = None
    max: float | None = None


class BBox(BaseModel):
    """Bounding box for spatial filtering."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class CacheFilterIn(BaseModel):
    """Input schema for cache filtering and pagination."""

    q: str | None = None
    type_id: PyObjectId | None = None
    size_id: PyObjectId | None = None
    country_id: PyObjectId | None = None
    state_id: PyObjectId | None = None
    difficulty: Range | None = None
    terrain: Range | None = None
    placed_after: dt.datetime | None = None
    placed_before: dt.datetime | None = None
    attr_pos: list[PyObjectId] | None = None
    attr_neg: list[PyObjectId] | None = None
    bbox: BBox | None = None
    sort: str | None = Field(
        default="-placed_at",
        description="e.g. -placed_at, -favorites, difficulty, terrain",
    )
    page: int = 1
    page_size: int = 50
