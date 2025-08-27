# backend/app/models/challenge.py
# Représentation d’un challenge et de ses métadonnées (cache d’origine, description, analytics).

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class ChallengeMeta(BaseModel):
    """Méta-statistiques d’un challenge.

    Description:
        Données analytiques facultatives destinées aux écrans de stats.

    Attributes:
        avg_days_to_complete (float | None): Jours moyens pour compléter.
        avg_caches_involved (float | None): Nombre moyen de caches impliquées.
        completions (int | None): Count de complétions.
        acceptance_rate (float | None): Taux d’acceptation.
    """
    avg_days_to_complete: Optional[float] = None
    avg_caches_involved: Optional[float] = None
    completions: Optional[int] = None
    acceptance_rate: Optional[float] = None

class ChallengeBase(BaseModel):
    """Champs de base d’un challenge.

    Description:
        Fait référence à la cache « mère » et porte le nom/description et méta.

    Attributes:
        cache_id (PyObjectId): Réf. `caches._id`.
        name (str): Nom du challenge.
        description (str | None): Description textuelle.
        meta (ChallengeMeta | None): Méta-statistiques optionnelles.
    """
    cache_id: PyObjectId                 # ref -> caches._id (cache "mère")
    name: str
    description: Optional[str] = None
    meta: Optional[ChallengeMeta] = None

class ChallengeCreate(ChallengeBase):
    """Payload de création d’un challenge.

    Description:
        Identique à `ChallengeBase` ; sert d’entrée pour l’API d’admin.
    """
    pass

class ChallengeUpdate(BaseModel):
    """Payload de mise à jour d’un challenge.

    Description:
        Mise à jour partielle des champs.

    Attributes:
        cache_id (PyObjectId | None): Nouvelle cache « mère ».
        name (str | None): Nouveau nom.
        description (str | None): Nouvelle description.
        meta (ChallengeMeta | None): Nouvelles méta-statistiques.
    """
    cache_id: Optional[PyObjectId] = None
    name: Optional[str] = None
    description: Optional[str] = None
    meta: Optional[ChallengeMeta] = None

class Challenge(MongoBaseModel, ChallengeBase):
    """Document Mongo d’un challenge.

    Description:
        Étend `ChallengeBase` avec _id, created_at, updated_at.
    """
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
