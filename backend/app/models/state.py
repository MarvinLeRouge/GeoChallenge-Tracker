# backend/app/api/models/state.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class StateBase(BaseModel):
    name: str
    code: Optional[str] = None  # ex: code INSEE ou similaire
    country_id: PyObjectId  # référence au pays

class StateCreate(StateBase):
    pass

class StateUpdate(BaseModel):
    name: Optional[str]
    code: Optional[str]
    country_id: Optional[PyObjectId]

class State(StateBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
