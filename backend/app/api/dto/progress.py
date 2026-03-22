# backend/app/models/progress_dto.py
# Transfer objects (output) for progress endpoints (snapshot + history).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.bson_utils import PyObjectId
from app.shared.progress import (
    ProgressSnapshot as AggregateProgress,
)


def _round_it(v: float, decimals: int = 0) -> float | None:
    """Rounding utility (pre-validation).

    Description:
        Converts the value to `float` and applies a `decimals`-place rounding; leaves `None` unchanged.

    Args:
        v (float): Value to round.
        decimals (int): Number of decimal places (default 0).

    Returns:
        float | None: Rounded value or None.
    """
    if v is None:
        return v
    return round(float(v), decimals)


class AggregateProgressOut(BaseModel):
    """Global aggregate returned by the API.

    Attributes:
        total (float): Current value.
        target (float): Target value.
        unit (str): Unit.
    """

    total: float
    target: float
    unit: str


class TaskProgressItemOut(BaseModel):
    """Per-task snapshot returned by the API.

    Description:
        Client-facing, ready to display: order, title, support flags, compiled signature,
        aggregate, counters/percent (rounded), diagnostics and timestamps.

    Attributes:
        task_id (PyObjectId): Task identifier.
        order (int): Task order within the challenge.
        title (str | None): Title (if available).
        supported_for_progress (bool): Included in global aggregates.
        compiled_signature (str): Stable signature or tag (‘override:done’, ‘unsupported:or-not’, …).
        aggregate (AggregateProgressOut | None): Task-specific aggregate.
        min_count (int): Expected threshold.
        current_count (int): Current measurement.
        percent (float): Progress (0–100, rounded to 1 decimal).
        notes (list[str]): Diagnostics.
        evaluated_in_ms (int): Evaluation duration.
        last_evaluated_at (datetime | None): Last evaluation.
        updated_at (datetime | None): Server last update.
        created_at (datetime | None): Creation date.
    """

    task_id: PyObjectId = Field(..., description="Id of the task")
    order: int = Field(..., ge=0, description="Task order within the challenge")
    title: str | None = Field(default=None, max_length=200)
    supported_for_progress: bool = Field(default=True)
    compiled_signature: str = Field(
        ...,
        description="Stable signature of compiled AND subtree, or a tag like 'override:done' / 'unsupported:or-not'",
    )
    aggregate: AggregateProgressOut | None = None

    # constraints & evaluation
    min_count: int = Field(..., ge=0)
    current_count: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)

    # diagnostics
    notes: list[str] = Field(default_factory=list)
    evaluated_in_ms: int = Field(default=0, ge=0)

    # projection
    start_found_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    estimated_completion_at: dt.datetime | None = None

    # server bookkeeping (optional)
    last_evaluated_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
    created_at: dt.datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

    _round_percent = field_validator("percent", mode="before")(lambda v: _round_it(v, 1))


class ProgressOut(BaseModel):
    """Full snapshot returned by the API.

    Attributes:
        id (PyObjectId | None): Alias for `_id`.
        user_challenge_id (PyObjectId): Target UserChallenge.
        checked_at (datetime): Snapshot timestamp.
        aggregate (AggregateProgress): Global aggregate.
        tasks (list[TaskProgressItemOut]): Per-task details.
        message (str | None): Optional annotation.
        created_at (datetime | None): Server audit trail.
    """

    id: PyObjectId | None = Field(default=None, alias="_id")
    user_challenge_id: PyObjectId

    # Time axis
    checked_at: dt.datetime = Field(...)

    # Aggregated state over all supported tasks
    aggregate: AggregateProgress

    # Per-task progress at this time
    tasks: list[TaskProgressItemOut] = Field(default_factory=list)

    # Optional annotations
    message: str | None = None

    # Projection
    estimated_completion_at: dt.datetime | None = None

    # Auditing
    created_at: dt.datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressHistoryItemOut(BaseModel):
    """Lightweight history entry (timeline).

    Attributes:
        checked_at (datetime): Entry timestamp.
        aggregate (AggregateProgress): Aggregate at that point in time.
    """

    checked_at: dt.datetime
    aggregate: AggregateProgress

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressGetResponse(BaseModel):
    """Response for GET /my/challenges/{uc_id}/progress.

    Attributes:
        latest (ProgressOut | None): Most recent available snapshot.
        history (list[ProgressHistoryItemOut]): Short history.
    """

    latest: ProgressOut | None = None
    history: list[ProgressHistoryItemOut] = Field(default_factory=list)


class ProgressEvaluateResponse(ProgressOut):
    """Response for POST /my/challenges/{uc_id}/progress/evaluate.

    Description:
        Inherits from `ProgressOut` (full snapshot).
    """

    pass
