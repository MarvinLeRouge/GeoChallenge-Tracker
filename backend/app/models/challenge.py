# backend/app/api/models/challenge.py

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class ChallengeMeta(BaseModel):
    avg_days_to_complete: Optional[float] = None
    avg_caches_involved: Optional[float] = None
    completions: Optional[int] = None
    acceptance_rate: Optional[float] = None

class ChallengeBase(BaseModel):
    cache_id: PyObjectId                 # ref -> caches._id (cache "mère")
    name: str
    description: Optional[str] = None
    meta: Optional[ChallengeMeta] = None

class ChallengeCreate(ChallengeBase):
    pass

class ChallengeUpdate(BaseModel):
    cache_id: Optional[PyObjectId] = None
    name: Optional[str] = None
    description: Optional[str] = None
    meta: Optional[ChallengeMeta] = None

class Challenge(MongoBaseModel, ChallengeBase):
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
