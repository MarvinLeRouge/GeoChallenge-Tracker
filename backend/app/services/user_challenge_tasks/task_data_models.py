# backend/app/services/user_challenge_tasks/task_data_models.py
# Task data models — exact preservation.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId
from app.domain.models.challenge_ast import TaskExpression


class PatchTaskItem(BaseModel):
    """Internal payload for task patch/put.

    CLASS IDENTICAL TO THE ORIGINAL — no changes.

    Attributes:
        _id (PyObjectId | None): Existing id (if updating).
        user_challenge_id (PyObjectId): Parent UC.
        order (int): Display order.
        expression (TaskExpression): Canonical AST.
        constraints (dict): Constraints.
        metrics (dict): Metrics.
        notes (str | None): Notes.
    """

    _id: PyObjectId | None = None
    user_challenge_id: PyObjectId
    order: int = 0
    expression: TaskExpression
    constraints: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
