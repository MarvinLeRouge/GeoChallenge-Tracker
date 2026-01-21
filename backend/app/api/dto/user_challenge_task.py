# backend/app/models/user_challenge_task_dto.py
# Schémas d’entrée/sortie pour gérer/valider les tâches d’un UserChallenge.

from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId
from app.domain.models.challenge_ast import TaskExpression


class TaskIn(BaseModel):
    """Entrée pour une tâche.

    Attributes:
        id (PyObjectId | None): Id de tâche (si update).
        title (str | None): Titre (≤ 200).
        expression (TaskExpression): AST de la tâche.
        constraints (dict[str, Any]): Contraintes (ex. {'min_count': 4}).
        status (str | None): 'todo' | 'in_progress' | 'done' (optionnel).
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
    """Entrée PUT pour remplacer la liste complète de tâches.

    Attributes:
        tasks (conlist[TaskIn]): Liste de 0 à 50 tâches.
    """

    tasks: list[TaskIn] = Field(min_length=0, max_length=50, default_factory=list)


class TasksValidateIn(BaseModel):
    """Entrée POST de validation de tâches (sans persistance).

    Attributes:
        tasks (conlist[TaskIn]): Liste de 0 à 50 tâches à valider.
    """

    tasks: list[TaskIn] = Field(min_length=0, max_length=50, default_factory=list)


class TaskOut(BaseModel):
    """Sortie d’une tâche.

    Attributes:
        id (PyObjectId): Id de tâche.
        order (int): Ordre.
        title (str): Titre.
        expression (TaskExpression): AST.
        constraints (dict[str, Any]): Contraintes.
        status (str | None): Statut manuel.
        metrics (dict[str, Any] | None): Métriques.
        progress (dict[str, Any] | None): Snapshot courant.
        last_evaluated_at (datetime | None): Dernière évaluation.
        updated_at (datetime | None): MAJ.
        created_at (datetime | None): Création.
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
    """Réponse: liste de tâches.

    Attributes:
        tasks (list[TaskOut]): Tâches ordonnées.
    """

    tasks: list[TaskOut]


class ValidationErrorItem(BaseModel):
    """Erreur de validation (itemisée).

    Attributes:
        index (int): Index dans la liste d’entrée.
        field (str): Champ concerné.
        code (str): Code d’erreur.
        message (str): Message lisible.
    """

    index: int
    field: str
    code: str
    message: str


class TasksValidateResponse(BaseModel):
    """Résultat de validation.

    Attributes:
        ok (bool): True si aucune erreur.
        errors (list[ValidationErrorItem]): Erreurs détaillées.
    """

    ok: bool
    errors: list[ValidationErrorItem] = []


# --- Rebuild Pydantic models to resolve forward/circular refs (Pydantic v2) ---
TaskOut.model_rebuild()
TasksListResponse.model_rebuild()
