from pydantic import BaseModel, Field
from typing import Optional, List
import datetime as dt
from app.core.bson_utils import *

class ProgressPoint(BaseModel):
    date: datetime
    value: int   # nombre de caches validées à ce moment

class ProgressBase(BaseModel):
    user_id: PyObjectId
    task_id: PyObjectId

    current_value: int = 0
    goal: int                # cible à atteindre

    # Série temporelle d’historique de progression
    time_series: Optional[List[ProgressPoint]] = []

    # Estimation (facultative)
    estimated_completion_date: Optional[dt.datetime] = None

    # Indice de pertinence de la projection (pas encore implémenté)
    prediction_score: Optional[float] = None

class ProgressCreate(ProgressBase):
    pass

class ProgressUpdate(BaseModel):
    current_value: Optional[int]
    time_series: Optional[List[ProgressPoint]]
    estimated_completion_date: Optional[dt.datetime]
    prediction_score: Optional[float]

class Progress(ProgressBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
