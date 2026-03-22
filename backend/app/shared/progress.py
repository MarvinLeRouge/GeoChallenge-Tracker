# backend/app/models/_shared.py
# Common types used by multiple models (e.g. ProgressSnapshot).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import PyObjectId
from app.core.utils import now


class ProgressSnapshot(BaseModel):
    """Aggregated progress snapshot.

    Description:
        Represents the current state of a set of tasks (for a challenge or a task),
        with overall percentage, number of completed tasks, and total count.

    Attributes:
        percent (float): Overall progress (0–100).
        tasks_done (int): Number of completed tasks.
        tasks_total (int): Total number of tasks.
        checked_at (datetime): Calculation timestamp (local).

    Returns:
        ProgressSnapshot: Object ready to serialize (ObjectId encoding handled).
    """

    percent: float = 0.0
    tasks_done: int = 0
    tasks_total: int = 0
    checked_at: dt.datetime = Field(default_factory=lambda: now())

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )
