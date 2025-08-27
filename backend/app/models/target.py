# backend/app/models/target.py
# Représente une cache candidate (target) pour un UserChallenge, avec scoring, géo et diagnostics.

from __future__ import annotations

from typing import Optional, List, Dict, Any
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict

from app.core.utils import utcnow
from app.core.bson_utils import PyObjectId, MongoBaseModel


# ---------- Diagnostics structurés ----------

class TargetDiagnosticsSubscores(BaseModel):
    """Sous-scores de diagnostic (0–1).

    Attributes:
        tasks (float): Part des tâches non terminées couvertes.
        urgency (float): Urgence (max ratio remaining/min_count).
        geo (float): Facteur distance (1 si pas de contrainte géo).
    """
    tasks: float = Field(ge=0.0, le=1.0)    # part des tasks non-done couvertes par la cache
    urgency: float = Field(ge=0.0, le=1.0)  # max ratio (remaining/min_count) parmi les tasks couvertes
    geo: float = Field(ge=0.0, le=1.0)      # facteur distance (1/(1+d/D0)) ou 1 si pas de géo

class TargetDiagnostics(BaseModel):
    """Bloc de diagnostic complet.

    Description:
        Détaille les tâches satisfaites et les sous-scores utilisés pour le tri/scoring.

    Attributes:
        matched (list[dict]): Détails des correspondances (internes debug).
        subscores (TargetDiagnosticsSubscores): Sous-scores de la target.
        evaluated_at (datetime): Timestamp UTC du calcul.
    """
    matched: List[Dict[str, Any]] = Field(default_factory=list)
    subscores: TargetDiagnosticsSubscores
    evaluated_at: dt.datetime = Field(default_factory=utcnow)

    model_config = ConfigDict(
        json_encoders={PyObjectId: str}
    )


# Schéma Mongo "targets"
# - 1 document par (user_challenge_id, cache_id)
# - dénormalisation minimale de la position (GeoJSON Point) pour $geoNear

class TargetCreate(BaseModel):
    """Payload d’upsert d’une target.

    Attributes:
        user_id (PyObjectId): Réf. utilisateur.
        user_challenge_id (PyObjectId): Réf. UC.
        cache_id (PyObjectId): Réf. cache candidate.
        primary_task_id (PyObjectId): Tâche principalement satisfaite.
        satisfies_task_ids (list[PyObjectId]): Autres tâches satisfaites.
        score (float | None): Score de tri.
        reasons (list[str] | None): Raisons textuelles.
        pinned (bool): Épinglée par l’utilisateur.
        loc (dict | None): GeoJSON Point `[lon, lat]`.
        diagnostics (TargetDiagnostics | None): Diagnostic interne.
    """
    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)

    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: Optional[Dict[str, Any]] = None

    # utile en debug, jamais exposé côté API publique
    diagnostics: Optional[TargetDiagnostics] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class TargetUpdate(BaseModel):
    """Payload de mise à jour d’une target.

    Attributes:
        satisfies_task_ids (list[PyObjectId] | None): Ajustements de couverture.
        score (float | None): Nouveau score.
        reasons (list[str] | None): Nouvelles raisons.
        pinned (bool | None): Épinglage.
        loc (dict | None): Point GeoJSON.
        diagnostics (TargetDiagnostics | None): Diagnostic.
        updated_at (datetime | None): Timestamp MAJ.
    """
    satisfies_task_ids: Optional[List[PyObjectId]] = None
    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: Optional[bool] = None
    loc: Optional[Dict[str, Any]] = None
    diagnostics: Optional[TargetDiagnostics] = None
    updated_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class Target(MongoBaseModel):
    """Document Mongo d’une target.

    Description:
        1 document par couple (user_challenge_id, cache_id). Dénormalise la position pour les requêtes géo.

    Attributes:
        user_id (PyObjectId): Réf. utilisateur.
        user_challenge_id (PyObjectId): Réf. UC.
        cache_id (PyObjectId): Réf. cache.
        primary_task_id (PyObjectId): Tâche principale.
        satisfies_task_ids (list[PyObjectId]): Tâches couvertes.
        score (float | None): Score.
        reasons (list[str] | None): Raisons.
        pinned (bool): Épinglée.
        loc (dict | None): GeoJSON Point.
        diagnostics (TargetDiagnostics | None): Diagnostic.
        created_at (datetime): Création (UTC).
        updated_at (datetime | None): MAJ (UTC).
    """
    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)

    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: Optional[Dict[str, Any]] = None

    diagnostics: Optional[TargetDiagnostics] = None

    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )
