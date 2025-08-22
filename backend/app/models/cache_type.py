# backend/app/models/cache_type.py

from __future__ import annotations
from typing import Optional, List
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class CacheTypeBase(BaseModel):
    name: str                     # ex: "Traditional", "Mystery", etc.
    code: Optional[str] = None    # abréviation, ex: "TR", "MY", "EV"
    aliases: List[str] = Field(default_factory=list)

class CacheTypeCreate(CacheTypeBase):
    pass

class CacheTypeUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    aliases: Optional[List[str]] = None

class CacheType(MongoBaseModel, CacheTypeBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
