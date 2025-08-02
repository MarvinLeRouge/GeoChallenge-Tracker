from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from app.core.bson_utils import *

class FoundCacheBase(BaseModel):
    user_id: PyObjectId         # référence à users._id
    cache_id: PyObjectId        # référence à caches._id
    found_date: date            # date de log (format YYYY-MM-DD)
    notes: Optional[str] = None

class FoundCacheCreate(FoundCacheBase):
    pass

class FoundCacheUpdate(BaseModel):
    notes: Optional[str] = None

class FoundCache(FoundCacheBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
