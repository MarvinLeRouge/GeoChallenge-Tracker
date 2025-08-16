# backend/app/api/models/cache.py

from __future__ import annotations
from typing import Optional, List, Literal, Dict, Any
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class CacheAttributeRef(BaseModel):
    attribute_doc_id: PyObjectId   # référence à cache_attributes._id
    is_positive: bool              # attribut positif (True) ou négatif (False)

class CacheBase(BaseModel):
    GC: str
    title: str
    description_html: Optional[str] = None
    url: Optional[str] = None

    # Typage / classement
    type_id: Optional[PyObjectId] = None      # ref -> CacheType
    size_id: Optional[PyObjectId] = None      # ref -> CacheSize

    # Localisation
    country_id: Optional[PyObjectId] = None   # ref -> Country
    state_id: Optional[PyObjectId] = None     # ref -> State
    lat: Optional[float] = None
    lon: Optional[float] = None
    elevation: Optional[int] = None           # en mètres (optionnel)
    location_more: Optional[Dict[str, Any]] = None  # infos libres (ville, département...)

    # Caractéristiques
    difficulty: Optional[float] = None        # 1.0 .. 5.0
    terrain: Optional[float] = None           # 1.0 .. 5.0
    attributes: List[CacheAttributeRef] = Field(default_factory=list)

    # Dates & stats
    placed_at: Optional[dt.datetime] = None
    favorites: Optional[int] = None
    status: Optional[Literal["active", "disabled", "archived"]] = None

class CacheCreate(CacheBase):
    pass

class CacheUpdate(BaseModel):
    # champs modifiables usuels (étends au besoin)
    title: Optional[str] = None
    description_html: Optional[str] = None
    url: Optional[str] = None
    elevation: Optional[int] = None
    state_id: Optional[PyObjectId] = None
    location_more: Optional[Dict[str, Any]] = None
    attributes: Optional[List[CacheAttributeRef]] = None
    status: Optional[Literal["active", "disabled", "archived"]] = None

class Cache(MongoBaseModel, CacheBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
