from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
