# backend/app/api/models/user_challenge_task.py

from __future__ import annotations
import datetime as dt
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import *

class AttributeSelector(BaseModel):
    cache_attribute_id: int
    is_positive: bool = True

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

class TaskExpression(BaseModel):
    # Logical nodes (use aliases to expose JSON keys 'and'/'or'/'not')
    and_: Optional[List['TaskExpression']] = Field(default=None, alias="and")
    or_: Optional[List['TaskExpression']] = Field(default=None, alias="or")
    not_: Optional['TaskExpression'] = Field(default=None, alias="not")

    # Predicates
    type_in: Optional[List[str]] = None
    placed_year: Optional[int] = None
    placed_before: Optional[dt.date] = None
    placed_after: Optional[dt.date] = None
    state_in: Optional[List[str]] = None
    country_is: Optional[str] = None
    difficulty_between: Optional[Tuple[float, float]] = None
    terrain_between: Optional[Tuple[float, float]] = None
    attributes: Optional[List[AttributeSelector]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

TaskExpression.model_rebuild()

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
