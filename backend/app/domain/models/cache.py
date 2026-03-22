# backend/app/models/cache.py
# Main geocache model (metadata, type, location, attributes, stats).

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class CacheAttributeRef(BaseModel):
    """Cache attribute reference.

    Description:
        Link to a `cache_attributes` document with direction indicator (positive/negative).

    Attributes:
        attribute_doc_id (PyObjectId): Reference to `cache_attributes._id`.
        is_positive (bool): True if the attribute is affirmative, False if negative.
    """

    attribute_doc_id: PyObjectId  # reference to cache_attributes._id
    is_positive: bool  # positive attribute (True) or negative (False)

    # Sub-model: add model_config to handle PyObjectId everywhere (nested)
    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={PyObjectId: str})


class CacheBase(BaseModel):
    """Base geocache fields.

    Description:
        Common structure for cache creation/reading: GC identifiers, type,
        location (lat/lon + GeoJSON), attributes, difficulty/terrain, dates and stats.

    Attributes:
        GC (str): Unique cache code (e.g. "GC123AB").
        title (str): Public title.
        description_html (str | None): HTML description.
        url (str | None): Source URL (e.g. listing).
        type_id (PyObjectId | None): Ref to `CacheType`.
        size_id (PyObjectId | None): Ref to `CacheSize`.
        country_id (PyObjectId | None): Ref to `Country`.
        state_id (PyObjectId | None): Ref to state/region.
        lat (float | None): Decimal latitude.
        lon (float | None): Decimal longitude.
        loc (dict[str, Any] | None): GeoJSON Point `[lon, lat]` for 2dsphere.
        elevation (int | None): Altitude in meters.
        location_more (dict[str, Any] | None): Free-form location details (city, department…).
        difficulty (float | None): Rating 1.0–5.0.
        terrain (float | None): Rating 1.0–5.0.
        attributes (list[CacheAttributeRef]): Attributes (positive/negative).
        placed_at (datetime | None): Cache placement date/time.
        owner (str | None): Owner (text).
        favorites (int | None): Favorite count.
        status (Literal[‘active’,’disabled’,’archived’] | None): Status.
    """

    GC: str
    title: str
    description_html: str | None = None
    url: str | None = None

    # Type / classification
    type_id: PyObjectId | None = None  # ref -> CacheType
    size_id: PyObjectId | None = None  # ref -> CacheSize

    # Location
    country_id: PyObjectId | None = None  # ref -> Country
    state_id: PyObjectId | None = None  # ref -> State
    lat: float | None = None
    lon: float | None = None
    # GeoJSON for 2dsphere index (coordinates [lon, lat])
    loc: dict[str, Any] | None = None
    elevation: int | None = None  # in meters (optional)
    location_more: dict[str, Any] | None = None  # free-form location info (city, department...)

    # Characteristics
    difficulty: float | None = None  # 1.0 .. 5.0
    terrain: float | None = None  # 1.0 .. 5.0
    attributes: list[CacheAttributeRef] = Field(default_factory=list)

    # Dates & stats
    placed_at: dt.datetime | None = None
    owner: str | None = None
    favorites: int | None = None
    status: Literal["active", "disabled", "archived"] | None = None


class CacheCreate(CacheBase):
    """Geocache creation payload.

    Description:
        Identical to `CacheBase`; used as input for the creation/import API.
    """

    pass


class CacheUpdate(BaseModel):
    """Partial geocache update payload.

    Description:
        Common updatable fields (title, description, elevation, state, attributes, status).

    Attributes:
        title (str | None): New title.
        description_html (str | None): New description.
        url (str | None): New URL.
        elevation (int | None): New altitude.
        state_id (PyObjectId | None): State/region.
        location_more (dict[str, Any] | None): Free-form location details.
        attributes (list[CacheAttributeRef] | None): New attribute list.
        status (Literal[‘active’,’disabled’,’archived’] | None): New status.
    """

    title: str | None = None
    description_html: str | None = None
    url: str | None = None
    elevation: int | None = None
    state_id: PyObjectId | None = None
    location_more: dict[str, Any] | None = None
    attributes: list[CacheAttributeRef] | None = None
    status: Literal["active", "disabled", "archived"] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={PyObjectId: str})


class Cache(MongoBaseModel, CacheBase):
    """Geocache Mongo document (with timestamps).

    Description:
        Extends `CacheBase` with audit fields (_id, created_at, updated_at).
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
