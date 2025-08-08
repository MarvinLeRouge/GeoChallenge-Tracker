# backend/app/api/models/challenge.py

from pydantic import BaseModel, Field
from typing import Optional, List
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class ChallengeBase(BaseModel):
    name: str
    description: Optional[str] = None

    # Lien vers la cache associée
    cache_id: PyObjectId

    # Optionnel, mais peut aider : résumé ou lien vers les tasks
    task_ids: Optional[List[PyObjectId]] = []

class ChallengeCreate(ChallengeBase):
    pass

class ChallengeUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    cache_id: Optional[PyObjectId]
    task_ids: Optional[List[PyObjectId]]

class Challenge(ChallengeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
