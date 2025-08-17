# backend/app/models/_sharted.PyObjectId
 
from __future__ import annotations
from pydantic import BaseModel, Field
import datetime as dt
from app.core.bson_utils import *
from app.core.utils import *

class ProgressSnapshot(BaseModel):
    percent: float = 0.0
    tasks_done: int = 0
    tasks_total: int = 0
    checked_at: dt.datetime = Field(default_factory=lambda: now())

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

