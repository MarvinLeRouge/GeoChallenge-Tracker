# backend/app/api/models/target.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class TargetBase(BaseModel):
    user_id: PyObjectId
    task_id: PyObjectId
    cache_id: PyObjectId

    score: Optional[float] = None  # 0.0 à 1.0, futur usage
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

class TargetCreate(TargetBase):
    pass

class TargetUpdate(BaseModel):
    score: Optional[float]
    updated_at: Optional[dt.datetime]

class Target(TargetBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
