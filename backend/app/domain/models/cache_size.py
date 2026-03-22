# backend/app/models/cache_size.py
# Reference list of cache sizes (Small, Micro, Regular, …) with display order.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheSizeBase(BaseModel):
    """Cache size (reference data).

    Description:
        Size name/code and sort order.

    Attributes:
        name (str): Name (e.g. "Small", "Micro").
        code (str | None): Short code (e.g. "S", "M").
        aliases (list[str]): Recognized aliases for this size.
        order (int | None): Display order.
    """

    name: str  # e.g. "Small", "Micro", "Regular"
    code: str | None = None  # internal code or abbreviation (e.g. "S", "M")
    aliases: list[str] = Field(default_factory=list)  # recognized aliases for this size
    order: int | None = None  # cache size sort order


class CacheSizeCreate(CacheSizeBase):
    """Cache size creation payload.

    Description:
        Identical to `CacheSizeBase` for insertion into the reference data.
    """

    pass


class CacheSizeUpdate(BaseModel):
    """Cache size update payload.

    Description:
        Partial field update.

    Attributes:
        name (str | None): New name.
        code (str | None): New code.
        aliases (list[str] | None): New aliases.
        order (int | None): New order.
    """

    name: str | None = None
    code: str | None = None
    aliases: list[str] | None = None
    order: int | None = None


class CacheSize(MongoBaseModel, CacheSizeBase):
    """Cache size Mongo document (reference data).

    Description:
        Extends `CacheSizeBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
