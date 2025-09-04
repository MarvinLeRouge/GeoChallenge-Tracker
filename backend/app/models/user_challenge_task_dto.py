# backend/app/models/user_challenge_task_dto.py
# Schémas d’entrée/sortie pour gérer/valider les tâches d’un UserChallenge.

from __future__ import annotations
import datetime as dt
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, conlist
from datetime import datetime
from app.core.bson_utils import PyObjectId
from app.models.challenge_ast import TaskExpression

class TaskIn(BaseModel):
    """Entrée pour une tâche.

    Attributes:
        id (PyObjectId | None): Id de tâche (si update).
        title (str | None): Titre (≤ 200).
        expression (TaskExpression): AST de la tâche.
        constraints (dict[str, Any]): Contraintes (ex. {'min_count': 4}).
        status (str | None): 'todo' | 'in_progress' | 'done' (optionnel).
    """
    id: Optional[PyObjectId] = Field(default=None, description="Task id if updating")
    title: Optional[str] = Field(default=None, max_length=200)
    expression: TaskExpression = Field(..., description="AST expression for this task")
    constraints: Dict[str, Any] = Field(..., description="Ex: {'min_count': 4}")
    status: Optional[str] = Field(default=None, description="Optional manual status: 'todo' | 'in_progress' | 'done'")

class TasksPutIn(BaseModel):
    """Entrée PUT pour remplacer la liste complète de tâches.

    Attributes:
        tasks (conlist[TaskIn]): Liste de 0 à 50 tâches.
    """
    tasks: conlist(TaskIn, min_length=0, max_length=50)

class TasksValidateIn(BaseModel):
    """Entrée POST de validation de tâches (sans persistance).

    Attributes:
        tasks (conlist[TaskIn]): Liste de 0 à 50 tâches à valider.
    """
    tasks: conlist(TaskIn, min_length=0, max_length=50)

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
    constraints: Dict[str, Any]
    status: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    start_found_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None

    last_evaluated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class TasksListResponse(BaseModel):
    """Réponse: liste de tâches.

    Attributes:
        tasks (list[TaskOut]): Tâches ordonnées.
    """
    tasks: List[TaskOut]

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
    errors: List[ValidationErrorItem] = []

# --- Rebuild Pydantic models to resolve forward/circular refs (Pydantic v2) ---
TaskOut.model_rebuild()
TasksListResponse.model_rebuild()
