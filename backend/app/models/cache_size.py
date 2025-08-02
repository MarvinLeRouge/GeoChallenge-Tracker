from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.core.bson_utils import *

class CacheSizeBase(BaseModel):
    name: str                    # ex: "Small", "Micro", "Regular"
    code: Optional[str] = None   # code interne ou abbr (ex: "S", "M")

class CacheSizeCreate(CacheSizeBase):
    pass

class CacheSizeUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]

class CacheSize(CacheSizeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
