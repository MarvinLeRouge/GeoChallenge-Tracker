# backend/app/api/models/cache_size.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CacheSizeBase(BaseModel):
    name: str                    # ex: "Small", "Micro", "Regular"
    code: Optional[str] = None   # code interne ou abbr (ex: "S", "M")
    order: Optional[int] = None   # ordonnancement des cache sizes

class CacheSizeCreate(CacheSizeBase):
    pass

class CacheSizeUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]
    order: Optional[int]

class CacheSize(CacheSizeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
