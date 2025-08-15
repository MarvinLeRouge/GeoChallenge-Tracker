# backend/app/api/models/cache.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CacheAttributeRef(BaseModel):
    attribute_doc_id: PyObjectId   # référence à cache_attributes.id
    is_positive: bool          # L'attribut est-il positif ou négatif

class CacheBase(BaseModel):
    GC: str
    title: str
    description_html: Optional[str] = None
    owner: Optional[str] = None
    cache_type: PyObjectId  # e.g., "traditional", "mystery", ...
    cache_size: PyObjectId        # e.g., "small", "regular", ...
    difficulty: float
    terrain: float
    placed_date: dt.datetime
    latitude: float
    longitude: float
    elevation: Optional[int] = None
    state_id: Optional[PyObjectId] = None
    location_more: Optional[dict] = None
    attributes: Optional[List[CacheAttributeRef]] = []
    favorites: Optional[int] = None

class CacheCreate(CacheBase):
    pass  # tous les champs sont requis ou ont des valeurs par défaut

class CacheUpdate(BaseModel):
    elevation: Optional[int]
    state_id: Optional[PyObjectId]
    location_more: Optional[dict]

class Cache(CacheBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
