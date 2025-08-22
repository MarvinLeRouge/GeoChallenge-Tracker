# backend/app/models/found_cache.py

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class FoundCacheBase(BaseModel):
    user_id: PyObjectId         # référence à users._id
    cache_id: PyObjectId        # référence à caches._id
    found_date: dt.date         # date de log (jour précis)
    notes: Optional[str] = None

class FoundCacheCreate(FoundCacheBase):
    pass

class FoundCacheUpdate(BaseModel):
    notes: Optional[str] = None

class FoundCache(MongoBaseModel, FoundCacheBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
