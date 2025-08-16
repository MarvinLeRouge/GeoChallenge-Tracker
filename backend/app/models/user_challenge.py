# backend/app/api/models/user_challenge.py
from __future__ import annotations

import datetime as dt
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import *

class UCLogic(BaseModel):
    # IDs of UserChallengeTask documents combined via boolean ops
    and_: Optional[List[PyObjectId]] = Field(default=None, alias="and")
    or_: Optional[List[PyObjectId]] = Field(default=None, alias="or")
    not_: Optional[PyObjectId] = Field(default=None, alias="not")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

class UserChallenge(MongoBaseModel):
    user_id: PyObjectId
    challenge_id: PyObjectId
    status: Literal["pending", "accepted", "dismissed", "completed"] = "pending"
    logic: Optional[UCLogic] = None
    # Aggregated, current snapshot for the whole challenge (redundant with history in Progress collection)
    progress: Optional[ProgressSnapshot] = None
    notes: Optional[str] = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
