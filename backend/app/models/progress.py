# backend/app/api/models/progress.py

from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import ProgressSnapshot  # shared snapshot structure

"""
Progress data model - clarification

- A series is built by multiple documents over time.
- One Progress document represents one instant t for a given `user_challenge_id`.
  It freezes all intersections at that time:
    * the global state of the user challenge (`aggregate`),
    * the state of each task in that challenge (`tasks[]`).
- To draw time-series charts, query all Progress docs for a `user_challenge_id`,
  sort by `checked_at`, and read `aggregate` or each `tasks[i].progress`.
"""

class TaskProgressItem(BaseModel):
    """Snapshot for a single task at this instant t."""
    task_id: PyObjectId
    status: Literal["todo", "in_progress", "done"] = "todo"
    progress: ProgressSnapshot = Field(default_factory=ProgressSnapshot)
    metrics: Dict[str, Any] = Field(default_factory=dict)   # e.g. {"current_count": 17}
    constraints: Optional[Dict[str, Any]] = None            # optional copy, for audit/explanations

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class Progress(MongoBaseModel):
    """Full, immutable snapshot for a user_challenge at time t."""
    user_challenge_id: PyObjectId

    # Time axis for charts & projections
    checked_at: dt.datetime = Field(default_factory=lambda: now())

    # Aggregate state for the whole challenge
    aggregate: ProgressSnapshot = Field(default_factory=ProgressSnapshot)

    # Per-task snapshots at this instant (one item per task belonging to the user_challenge)
    tasks: List[TaskProgressItem] = Field(default_factory=list)

    # Optional annotations
    message: Optional[str] = None
    engine_version: Optional[str] = None

    # For auditing (append-only — no updated_at)
    created_at: dt.datetime = Field(default_factory=lambda: now())
