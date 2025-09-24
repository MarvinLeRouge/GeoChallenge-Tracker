# backend/app/models/user_challenge_task.py
# Tâche déclarée dans un UserChallenge : expression AST, contraintes, statut et métriques.

from __future__ import annotations

import datetime as dt

from pydantic import Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now
from app.models._shared import ProgressSnapshot
from app.models.challenge_ast import TaskExpression


class UserChallengeTask(MongoBaseModel):
    """Document Mongo « UserChallengeTask ».

    Description:
        Contient l’expression AST (sélecteur de caches), les contraintes (ex. min_count),
        le statut manuel, des métriques calculées et un snapshot de progression.

    Attributes:
        user_challenge_id (PyObjectId): Réf. UC parent.
        order (int): Ordre d’affichage.
        title (str): Titre de la tâche.
        expression (TaskExpression): AST de sélection.
        constraints (dict): Contraintes (ex. {'min_count': 4}).
        status (str): 'todo' | 'in_progress' | 'done'.
        metrics (dict): Métriques (ex. {'current_count': 3}).
        progress (ProgressSnapshot | None): Snapshot courant.
        last_evaluated_at (datetime | None): Dernière évaluation.
        created_at (datetime): Création (local).
        updated_at (datetime | None): MAJ.
    """

    user_challenge_id: PyObjectId
    order: int = 0
    title: str
    expression: TaskExpression
    constraints: dict = Field(default_factory=dict)  # ex: {"min_count": 4}
    status: str = Field(default="todo")  # todo | in_progress | done
    metrics: dict = Field(default_factory=dict)  # ex: {"current_count": 3}
    # Current aggregated snapshot for this task (history is in Progress collection)
    progress: ProgressSnapshot | None = None
    start_found_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None

    last_evaluated_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None


UserChallengeTask.model_rebuild()
