# backend/app/models/progress.py
# Progress snapshot models (global + per task) for a UserChallenge, with timestamps.

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now
from app.shared.progress import ProgressSnapshot  # shared snapshot structure

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
    """Per-task snapshot at time t.

    Description:
        Captures the state of a task at computation time (status, counters, diagnostics)
        to feed detailed views and the global aggregate.

    Attributes:
        task_id (PyObjectId): Task reference.
        status (Literal[‘todo’,’in_progress’,’done’]): Current state.
        progress (ProgressSnapshot): Sub-aggregate/percent for this task.
        metrics (dict[str, Any]): Computed counters/values (e.g. `current_count`).
        constraints (dict[str, Any] | None): Constraints copied for audit purposes.
        aggregate (AggregateProgress | None): Dedicated aggregate (e.g. specific units).
    """

    task_id: PyObjectId
    status: Literal["todo", "in_progress", "done"] = "todo"
    progress: ProgressSnapshot = Field(default_factory=ProgressSnapshot)
    metrics: dict[str, Any] = Field(default_factory=dict)  # e.g. {"current_count": 17}
    constraints: dict[str, Any] | None = None  # optional copy, for audit/explanations
    aggregate: AggregateProgress | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class Progress(MongoBaseModel):
    """Full snapshot of a UserChallenge at time t.

    Description:
        Immutable document describing the aggregated state of the challenge and each task,
        used for charts and history.

    Attributes:
        user_challenge_id (PyObjectId): Relevant UC reference.
        checked_at (datetime): Computation timestamp (time axis).
        aggregate (ProgressSnapshot): Global aggregate (all supported tasks).
        tasks (list[TaskProgressItem]): Per-task details.
        message (str | None): Optional annotation.
        engine_version (str | None): Evaluation engine version.
        created_at (datetime): Creation date (append-only).
    """

    user_challenge_id: PyObjectId

    # Time axis for charts & projections
    checked_at: dt.datetime = Field(default_factory=lambda: now())

    # Aggregate state for the whole challenge
    aggregate: ProgressSnapshot = Field(default_factory=ProgressSnapshot)

    # Per-task snapshots at this instant (one item per task belonging to the user_challenge)
    tasks: list[TaskProgressItem] = Field(default_factory=list)

    # Optional annotations
    message: str | None = None
    engine_version: str | None = None

    # For auditing (append-only — no updated_at)
    created_at: dt.datetime = Field(default_factory=lambda: now())


class AggregateProgress(BaseModel):
    """Simple aggregate (value/target/unit).

    Attributes:
        total (float): Current value.
        target (float): Expected target.
        unit (str): Unit (e.g. "points", "meters").
    """

    total: float = 0.0
    target: float = 0.0
    unit: str = "points"  # or "meters" for altitude

    model_config = ConfigDict(
        populate_by_name=True,
    )
