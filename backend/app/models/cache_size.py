# backend/app/models/cache_size.py

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class CacheSizeBase(BaseModel):
    name: str                    # ex: "Small", "Micro", "Regular"
    code: Optional[str] = None   # code interne ou abbr (ex: "S", "M")
    order: Optional[int] = None  # ordonnancement des cache sizes

class CacheSizeCreate(CacheSizeBase):
    pass

class CacheSizeUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    order: Optional[int] = None

class CacheSize(MongoBaseModel, CacheSizeBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
