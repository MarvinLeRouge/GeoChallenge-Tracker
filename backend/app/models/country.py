from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.core.bson_utils import *

class CountryBase(BaseModel):
    name: str                      # ex: "France"
    code: Optional[str] = None     # ex: "FR", "DE", ISO 3166-1 alpha-2

class CountryCreate(CountryBase):
    pass

class CountryUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]

class Country(CountryBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
