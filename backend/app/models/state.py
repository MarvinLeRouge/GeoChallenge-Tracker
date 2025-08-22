# backend/app/models/state.py

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class StateBase(BaseModel):
    name: str
    code: Optional[str] = None        # ex: code INSEE / abbr
    country_id: PyObjectId            # ref -> Country

class StateCreate(StateBase):
    pass

class StateUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    country_id: Optional[PyObjectId] = None

class State(MongoBaseModel, StateBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
