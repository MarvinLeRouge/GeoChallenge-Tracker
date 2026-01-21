# backend/app/models/progress.py
# Modèles de snapshot de progression (global + par tâche) pour un UserChallenge, horodatés.

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
    """Snapshot par tâche à l’instant t.

    Description:
        Capture l’état d’une tâche au moment du calcul (statut, compteurs, diagnostics)
        afin d’alimenter les vues détaillées et l’agrégat global.

    Attributes:
        task_id (PyObjectId): Réf. de la tâche.
        status (Literal['todo','in_progress','done']): État courant.
        progress (ProgressSnapshot): Sous-agrégat/percent pour cette tâche.
        metrics (dict[str, Any]): Compteurs/valeurs calculées (ex. `current_count`).
        constraints (dict[str, Any] | None): Contraintes copiées à des fins d’audit.
        aggregate (AggregateProgress | None): Agrégat dédié (ex. unités spécifiques).
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
    """Snapshot complet d’un UserChallenge à l’instant t.

    Description:
        Document immuable décrivant l’état agrégé du challenge et l’état de chaque tâche,
        utilisé pour les graphiques et l’historique.

    Attributes:
        user_challenge_id (PyObjectId): Réf. UC concerné.
        checked_at (datetime): Horodatage du calcul (axe temps).
        aggregate (ProgressSnapshot): Agrégat global (toutes tâches supportées).
        tasks (list[TaskProgressItem]): Détails par tâche.
        message (str | None): Annotation éventuelle.
        engine_version (str | None): Version du moteur d’évaluation.
        created_at (datetime): Date de création (append-only).
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
    """Agrégat simple (valeur/objectif/unité).

    Attributes:
        total (float): Valeur courante.
        target (float): Objectif attendu.
        unit (str): Unité (ex. "points", "meters").
    """

    total: float = 0.0
    target: float = 0.0
    unit: str = "points"  # ou "meters" pour altitude

    model_config = ConfigDict(
        populate_by_name=True,
    )
