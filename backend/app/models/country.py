# backend/app/api/models/country.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
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
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
