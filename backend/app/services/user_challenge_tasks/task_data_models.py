# backend/app/services/user_challenge_tasks/task_data_models.py
# Modèles de données pour les tâches - PRESERVATION EXACTE

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId
from app.domain.models.challenge_ast import TaskExpression


class PatchTaskItem(BaseModel):
    """Payload interne pour patch/put de tâche.

    CLASSE IDENTIQUE À L'ORIGINALE - Aucune modification.

    Attributes:
        _id (PyObjectId | None): Id existant (si update).
        user_challenge_id (PyObjectId): UC parent.
        order (int): Ordre d'affichage.
        expression (TaskExpression): AST canonique.
        constraints (dict): Contraintes.
        metrics (dict): Métriques.
        notes (str | None): Notes.
    """

    _id: PyObjectId | None = None
    user_challenge_id: PyObjectId
    order: int = 0
    expression: TaskExpression
    constraints: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
