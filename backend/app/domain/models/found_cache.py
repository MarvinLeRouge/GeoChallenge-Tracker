# backend/app/models/found_cache.py
# (User, cache) association with find date and optional notes.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class FoundCacheBase(BaseModel):
    """Cache find by a user.

    Attributes:
        user_id (PyObjectId): Ref to `users._id`.
        cache_id (PyObjectId): Ref to `caches._id`.
        found_date (date): Log date (specific day).
        notes (str | None): Optional notes.
    """

    user_id: PyObjectId  # reference to users._id
    cache_id: PyObjectId  # reference to caches._id
    found_date: dt.date  # log date (specific day)
    notes: str | None = None


class FoundCacheCreate(FoundCacheBase):
    """Cache find creation payload."""

    pass


class FoundCacheUpdate(BaseModel):
    """Cache find update payload.

    Attributes:
        notes (str | None): New notes.
    """

    notes: str | None = None


class FoundCache(MongoBaseModel, FoundCacheBase):
    """Cache find Mongo document.

    Description:
        Extends `FoundCacheBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
