# backend/app/models/user_profile_dto.py

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field

from app.core.utils import utcnow


class UserLocationIn(BaseModel):
    # Deux possibilités :
    # - lat/lon numériques
    # - ou position string (DD / DM / DMS)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    position: Optional[str] = None


class UserLocationOut(BaseModel):
    lat: float
    lon: float
    coords: Optional[str] = ""
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())
