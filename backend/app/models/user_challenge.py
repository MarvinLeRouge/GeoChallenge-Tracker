# backend/app/api/models/user_challenge.py

from __future__ import annotations
import datetime as dt
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.core.utils import *
from app.core.bson_utils import *
from app.models._shared import *
from app.models.challenge_ast import UCLogic

class UserChallenge(MongoBaseModel):
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
