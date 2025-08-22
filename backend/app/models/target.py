# backend/app/models/target.py

from __future__ import annotations
from typing import Optional, List, Dict, Any
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *

# A Target is a recommended cache for a given UserChallenge.
# It may satisfy multiple tasks simultaneously from that same UserChallenge.

class TargetCreate(BaseModel):
    user_challenge_id: PyObjectId
    cache_id: PyObjectId
    primary_task_id: PyObjectId
    # Include primary_task_id here as well so $all queries work uniformly.
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)
    score: Optional[float] = None
    diagnostics: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

class TargetUpdate(BaseModel):
    satisfies_task_ids: Optional[List[PyObjectId]] = None
    score: Optional[float] = None
    diagnostics: Optional[Dict[str, Any]] = None
    updated_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

class Target(MongoBaseModel):
    user_challenge_id: PyObjectId
    cache_id: PyObjectId
    primary_task_id: PyObjectId
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)
    score: Optional[float] = None
    diagnostics: Optional[Dict[str, Any]] = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
