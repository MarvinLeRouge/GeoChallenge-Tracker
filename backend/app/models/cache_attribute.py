# backend/app/api/models/attribute.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CacheAttributeBase(BaseModel):
    cache_attribute_id: int             # identifiant global, ex. 14
    txt: str                            # identifiant txt (ex. : dogs_allowed)
    name: str                           # libellé principal ("Dogs allowed")
    name_reverse: Optional[str] = None  # libellé inverse ("No dogs allowed")
    aliases: Optional[list[str]] = []

class CacheAttributeCreate(CacheAttributeBase):
    pass

class CacheAttributeUpdate(BaseModel):
    cache_attribute_id: Optional[int]
    name: Optional[str]
    name_reverse: Optional[str]
    aliases: Optional[list[str]]

class CacheAttribute(CacheAttributeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
