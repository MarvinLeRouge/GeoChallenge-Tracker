# backend/app/models/user_challenge_task_dto.py
# Input/output schemas for managing and validating UserChallenge tasks.

from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId
from app.domain.models.challenge_ast import TaskExpression


class TaskIn(BaseModel):
    """Task input.

    Attributes:
        id (PyObjectId | None): Task id (if updating).
        title (str | None): Title (≤ 200).
        expression (TaskExpression): Task AST.
        constraints (dict[str, Any]): Constraints (e.g. {'min_count': 4}).
        status (str | None): 'todo' | 'in_progress' | 'done' (optional).
    """

    id: PyObjectId | None = Field(default=None, description="Task id if updating")
    title: str | None = Field(default=None, max_length=200)
    expression: TaskExpression = Field(..., description="AST expression for this task")
    constraints: dict[str, Any] = Field(..., description="Ex: {'min_count': 4}")
    status: str | None = Field(
        default=None,
        description="Optional manual status: 'todo' | 'in_progress' | 'done'",
    )


class TasksPutIn(BaseModel):
    """PUT input to replace the complete task list.

    Attributes:
        tasks (conlist[TaskIn]): List of 0 to 50 tasks.
    """

    tasks: list[TaskIn] = Field(min_length=0, max_length=50, default_factory=list)


class TasksValidateIn(BaseModel):
    """POST input for task validation (without persistence).

    Attributes:
        tasks (conlist[TaskIn]): List of 0 to 50 tasks to validate.
    """

    tasks: list[TaskIn] = Field(min_length=0, max_length=50, default_factory=list)


class TaskOut(BaseModel):
    """Task output.

    Attributes:
        id (PyObjectId): Task id.
        order (int): Order.
        title (str): Title.
        expression (TaskExpression): AST.
        constraints (dict[str, Any]): Constraints.
        status (str | None): Manual status.
        metrics (dict[str, Any] | None): Metrics.
        progress (dict[str, Any] | None): Current snapshot.
        last_evaluated_at (datetime | None): Last evaluation.
        updated_at (datetime | None): Last update.
        created_at (datetime | None): Creation date.
    """

    id: PyObjectId
    order: int
    title: str
    expression: TaskExpression
    constraints: dict[str, Any]
    status: str | None = None
    metrics: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    start_found_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None

    last_evaluated_at: datetime | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class TasksListResponse(BaseModel):
    """Response: task list.

    Attributes:
        tasks (list[TaskOut]): Ordered tasks.
    """

    tasks: list[TaskOut]


class ValidationErrorItem(BaseModel):
    """Itemized validation error.

    Attributes:
        index (int): Index in the input list.
        field (str): Affected field.
        code (str): Error code.
        message (str): Human-readable message.
    """

    index: int
    field: str
    code: str
    message: str


class TasksValidateResponse(BaseModel):
    """Validation result.

    Attributes:
        ok (bool): True if no errors.
        errors (list[ValidationErrorItem]): Detailed errors.
    """

    ok: bool
    errors: list[ValidationErrorItem] = []


# --- Rebuild Pydantic models to resolve forward/circular refs (Pydantic v2) ---
TaskOut.model_rebuild()
TasksListResponse.model_rebuild()
