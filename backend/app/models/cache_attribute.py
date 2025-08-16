# backend/app/api/models/attribute.py
from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class CacheAttributeBase(BaseModel):
    cache_attribute_id: int             # identifiant global, ex. 14
    txt: str                            # identifiant txt (ex.: dogs_allowed)
    name: str                           # libellé principal ("Dogs allowed")
    name_reverse: Optional[str] = None  # libellé inverse ("No dogs allowed")
    aliases: List[str] = Field(default_factory=list)

class CacheAttributeCreate(CacheAttributeBase):
    pass

class CacheAttributeUpdate(BaseModel):
    cache_attribute_id: Optional[int] = None
    name: Optional[str] = None
    name_reverse: Optional[str] = None
    aliases: Optional[List[str]] = None

class CacheAttribute(MongoBaseModel, CacheAttributeBase):
    # Document stocké en base (hérite de MongoBaseModel pour _id/encoders)
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
