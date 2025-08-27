# backend/app/models/_shared.py
# Types communs utilisés par plusieurs modèles (ex. ProgressSnapshot).
 
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
import datetime as dt
from app.core.bson_utils import *
from app.core.utils import *

class ProgressSnapshot(BaseModel):
    """Snapshot agrégé de progression.

    Description:
        Représente l’état courant d’un ensemble de tâches (pour un challenge ou une tâche),
        avec pourcentage global, nombre de tâches terminées et total.

    Attributes:
        percent (float): Avancement global (0–100).
        tasks_done (int): Nombre de tâches terminées.
        tasks_total (int): Nombre total de tâches.
        checked_at (datetime): Timestamp de calcul (local).

    Returns:
        ProgressSnapshot: Objet prêt à sérialiser (encodage ObjectId géré).
    """
    percent: float = 0.0
    tasks_done: int = 0
    tasks_total: int = 0
    checked_at: dt.datetime = Field(default_factory=lambda: now())

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

