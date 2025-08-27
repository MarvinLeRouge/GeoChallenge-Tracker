# backend/app/models/progress_dto.py
# Objets de transfert (sortie) pour les endpoints de progression (snapshot + historique).

from __future__ import annotations

from typing import Optional, List
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.bson_utils import PyObjectId
from app.models._shared import ProgressSnapshot as AggregateProgress  # percent, tasks_done, tasks_total, checked_at


def _round_it(v: float, decimals: int = 0) -> float | None:
    """Arrondi utilitaire (pré-validation).

    Description:
        Convertit la valeur en `float` et applique un arrondi `decimals`; laisse `None` inchangé.

    Args:
        v (float): Valeur à arrondir.
        decimals (int): Nombre de décimales (défaut 0).

    Returns:
        float | None: Valeur arrondie ou None.
    """
    if v is None:
        return v
    return round(float(v), decimals)

class AggregateProgressOut(BaseModel):
    """Agrégat global renvoyé par l’API.

    Attributes:
        total (float): Valeur courante.
        target (float): Objectif.
        unit (str): Unité.
    """
    total: float
    target: float
    unit: str

class TaskProgressItemOut(BaseModel):
    """Snapshot par tâche renvoyé par l’API.

    Description:
        Vu « client », prêt à afficher : ordre, titre, drapeaux de support, signature compilée,
        agrégat, compteurs/percent (arrondi), diagnostics et timestamps.

    Attributes:
        task_id (PyObjectId): Identifiant de tâche.
        order (int): Ordre de la tâche dans le challenge.
        title (str | None): Titre (si disponible).
        supported_for_progress (bool): Inclus dans les agrégats globaux.
        compiled_signature (str): Empreinte stable ou tag ('override:done', 'unsupported:or-not', …).
        aggregate (AggregateProgressOut | None): Agrégat propre à la tâche.
        min_count (int): Seuil attendu.
        current_count (int): Mesure actuelle.
        percent (float): Avancement (0–100, arrondi à 1 décimale).
        notes (list[str]): Diagnostics.
        evaluated_in_ms (int): Durée d’évaluation.
        last_evaluated_at (datetime | None): Dernière évaluation.
        updated_at (datetime | None): MAJ serveur.
        created_at (datetime | None): Création.
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

    _round_percent = field_validator("percent", mode="before")(lambda v: _round_it(v, 1))

class ProgressOut(BaseModel):
    """Snapshot complet renvoyé par l’API.

    Attributes:
        id (PyObjectId | None): Alias `_id`.
        user_challenge_id (PyObjectId): UC visé.
        checked_at (datetime): Horodatage du snapshot.
        aggregate (AggregateProgress): Agrégat global.
        tasks (list[TaskProgressItemOut]): Détails par tâche.
        message (str | None): Annotation éventuelle.
        created_at (datetime | None): Traçabilité serveur.
    """
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

    # Auditing
    created_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressHistoryItemOut(BaseModel):
    """Entrée légère d’historique (timeline).

    Attributes:
        checked_at (datetime): Timestamp de l’entrée.
        aggregate (AggregateProgress): Agrégat à cet instant.
    """
    checked_at: dt.datetime
    aggregate: AggregateProgress

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class ProgressGetResponse(BaseModel):
    """Réponse GET /my/challenges/{uc_id}/progress.

    Attributes:
        latest (ProgressOut | None): Dernier snapshot disponible.
        history (list[ProgressHistoryItemOut]): Historique court.
    """
    latest: Optional[ProgressOut] = None
    history: List[ProgressHistoryItemOut] = Field(default_factory=list)


class ProgressEvaluateResponse(ProgressOut):
    """Réponse POST /my/challenges/{uc_id}/progress/evaluate.

    Description:
        Hérite de `ProgressOut` (snapshot complet).
    """
    pass
