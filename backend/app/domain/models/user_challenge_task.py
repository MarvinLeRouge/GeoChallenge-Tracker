# backend/app/models/user_challenge_task.py
# Task declared within a UserChallenge: AST expression, constraints, status and metrics.

from __future__ import annotations

import datetime as dt

from pydantic import Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now
from app.domain.models.challenge_ast import TaskExpression
from app.shared.progress import ProgressSnapshot


class UserChallengeTask(MongoBaseModel):
    """UserChallengeTask Mongo document.

    Description:
        Contains the AST expression (cache selector), constraints (e.g. min_count),
        manual status, computed metrics and a progress snapshot.

    Attributes:
        user_challenge_id (PyObjectId): Parent UC reference.
        order (int): Display order.
        title (str): Task title.
        expression (TaskExpression): Selection AST.
        constraints (dict): Constraints (e.g. {‘min_count’: 4}).
        status (str): ‘todo’ | ‘in_progress’ | ‘done’.
        metrics (dict): Metrics (e.g. {‘current_count’: 3}).
        progress (ProgressSnapshot | None): Current snapshot.
        last_evaluated_at (datetime | None): Last evaluation.
        created_at (datetime): Creation time (local).
        updated_at (datetime | None): Last update.
    """

    user_challenge_id: PyObjectId
    order: int = 0
    title: str
    expression: TaskExpression
    constraints: dict = Field(default_factory=dict)  # e.g. {"min_count": 4}
    status: str = Field(default="todo")  # todo | in_progress | done
    metrics: dict = Field(default_factory=dict)  # e.g. {"current_count": 3}
    # Current aggregated snapshot for this task (history is in Progress collection)
    progress: ProgressSnapshot | None = None
    start_found_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None

    last_evaluated_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None


UserChallengeTask.model_rebuild()
