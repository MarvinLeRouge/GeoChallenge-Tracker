# backend/app/models/user_challenge_task.py

from __future__ import annotations
import datetime as dt
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import *
from app.models.challenge_ast import TaskExpression

class UserChallengeTask(MongoBaseModel):
    user_challenge_id: PyObjectId
    order: int = 0
    title: str
    expression: TaskExpression
    constraints: dict = Field(default_factory=dict)  # ex: {"min_count": 4}
    status: str = Field(default="todo")              # todo | in_progress | done
    metrics: dict = Field(default_factory=dict)      # ex: {"current_count": 3}
    # Current aggregated snapshot for this task (history is in Progress collection)
    progress: Optional[ProgressSnapshot] = None

    last_evaluated_at: Optional[dt.datetime] = None
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
