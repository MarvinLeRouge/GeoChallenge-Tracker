# backend/app/api/models/cache.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CacheBase(BaseModel):
    GC: str
    title: str
    cache_type: PyObjectId  # e.g., "traditional", "mystery", ...
    size: PyObjectId        # e.g., "small", "regular", ...
    difficulty: float
    terrain: float
    placed_date: datetime
    latitude: float
    longitude: float
    elevation: Optional[int] = None
    county_id: Optional[PyObjectId] = None
    location_more: Optional[dict] = None
    attributes: Optional[List[PyObjectId]] = []

class CacheCreate(CacheBase):
    pass  # tous les champs sont requis ou ont des valeurs par défaut

class CacheUpdate(BaseModel):
    elevation: Optional[int]
    country_id: Optional[PyObjectId]
    county_id: Optional[PyObjectId]
    location_more: Optional[dict]

class Cache(CacheBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
