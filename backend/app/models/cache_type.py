from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.bson_utils import *

class CacheTypeBase(BaseModel):
    name: str                  # ex: "Traditional", "Mystery", etc.
    code: Optional[str] = None # abréviation, ex: "TR", "MY", "EV"

class CacheTypeCreate(CacheTypeBase):
    pass

class CacheTypeUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]

class CacheType(CacheTypeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
