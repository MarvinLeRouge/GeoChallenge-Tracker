# backend/app/models/progress_dto.py

from __future__ import annotations

from typing import Optional, List
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict
from app.core.bson_utils import PyObjectId
from app.models._shared import ProgressSnapshot as AggregateProgress  # percent, tasks_done, tasks_total, checked_at


class AggregateProgressOut(BaseModel):
    total: float
    target: float
    unit: str

class TaskProgressItemOut(BaseModel):
    """Per-task snapshot returned by the progress endpoints.

    Notes:
      - `supported_for_progress` marks tasks that are included in aggregates (MVP: AND-only).
      - `compiled_signature` helps clients detect when a task definition changed.
    """
    task_id: PyObjectId = Field(..., description="Id of the task")
    order: int = Field(..., ge=0, description="Task order within the challenge")
    title: Optional[str] = Field(default=None, max_length=200)
    supported_for_progress: bool = Field(default=True)
    compiled_signature: str = Field(..., description="Stable signature of compiled AND subtree, or a tag like 'override:done' / 'unsupported:or-not'")
    aggregate: Optional[AggregateProgressOut] = None

    # constraints & evaluation
    min_count: int = Field(..., ge=0)
    current_count: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)

    # diagnostics
    notes: List[str] = Field(default_factory=list)
    evaluated_in_ms: int = Field(default=0, ge=0)

    # server bookkeeping (optional)
    last_evaluated_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressOut(BaseModel):
    """A full snapshot document for a given user_challenge at time t."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_challenge_id: PyObjectId

    # Time axis
    checked_at: dt.datetime = Field(...)

    # Aggregated state over all supported tasks
    aggregate: AggregateProgress

    # Per-task progress at this time
    tasks: List[TaskProgressItemOut] = Field(default_factory=list)

    # Optional annotations
    message: Optional[str] = None
    engine_version: Optional[str] = None

    # Auditing
    created_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressHistoryItemOut(BaseModel):
    """Lightweight entry for history lists (timeline)."""
    checked_at: dt.datetime
    aggregate: AggregateProgress

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressGetResponse(BaseModel):
    """Response for GET /my/challenges/{uc_id}/progress"""
    latest: Optional[ProgressOut] = None
    history: List[ProgressHistoryItemOut] = Field(default_factory=list)


class ProgressEvaluateResponse(ProgressOut):
    """Response for POST /my/challenges/{uc_id}/progress/evaluate"""
    pass
