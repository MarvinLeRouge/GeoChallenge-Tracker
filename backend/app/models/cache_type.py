# backend/app/api/models/cache_type.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CacheTypeBase(BaseModel):
    name: str                  # ex: "Traditional", "Mystery", etc.
    code: Optional[str] = None # abréviation, ex: "TR", "MY", "EV"
    aliases: Optional[list[str]] = []

class CacheTypeCreate(CacheTypeBase):
    pass

class CacheTypeUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]
    aliases: Optional[list[str]]

class CacheType(CacheTypeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
