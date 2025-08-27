# backend/app/models/user_challenge.py
# État d’un challenge pour un utilisateur (statuts déclarés/calculés, logique UC, notes, progress).

from __future__ import annotations
import datetime as dt
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import *
from app.models.challenge_ast import UCLogic

class UserChallenge(MongoBaseModel):
    """Document Mongo « UserChallenge ».

    Description:
        Lie un utilisateur à un challenge, stocke le statut utilisateur (déclaratif) et le
        statut calculé (évaluation UC logic), ainsi que l’override manuel et un snapshot courant.

    Attributes:
        user_id (PyObjectId): Réf. utilisateur.
        challenge_id (PyObjectId): Réf. challenge.
        status (Literal['pending','accepted','dismissed','completed']): Statut déclaré.
        computed_status (Literal[...] | None): Statut calculé.
        manual_override (bool): Override manuel actif.
        override_reason (str | None): Justification d’override.
        overridden_at (datetime | None): Date override.
        logic (UCLogic | None): Logique d’agrégation des tasks.
        progress (ProgressSnapshot | None): Snapshot global courant.
        notes (str | None): Notes libres.
        created_at (datetime): Création (local).
        updated_at (datetime | None): MAJ.
    """
    user_id: PyObjectId
    challenge_id: PyObjectId
    # Déclaration UTILISATEUR (peut être "completed" même si non satisfaisant algorithmiquement)
    status: Literal["pending", "accepted", "dismissed", "completed"] = "pending"

    # Statut CALCULÉ par l’évaluation (UCLogic sur les tasks)
    computed_status: Optional[Literal["pending", "accepted", "dismissed", "completed"]] = None

    # Traçabilité de l’override
    manual_override: bool = False
    override_reason: Optional[str] = None
    overridden_at: Optional[dt.datetime] = None
    logic: Optional[UCLogic] = None
    # Aggregated, current snapshot for the whole challenge (redundant with history in Progress collection)
    progress: Optional[ProgressSnapshot] = None
    notes: Optional[str] = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
