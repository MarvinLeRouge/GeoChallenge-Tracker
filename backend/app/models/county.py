from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.bson_utils import *

class CountyBase(BaseModel):
    name: str
    code: Optional[str] = None  # ex: code INSEE ou similaire
    country_id: PyObjectId  # référence au pays

class CountyCreate(CountyBase):
    pass

class CountyUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]
    country_id: Optional[PyObjectId]

class County(CountyBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
