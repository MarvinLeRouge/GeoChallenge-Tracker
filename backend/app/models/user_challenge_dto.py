# backend/app/models/user_challenge_dto.py
# Schémas I/O pour les routes « mes challenges » (liste, détail, patch).

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.bson_utils import PyObjectId

class PatchUCIn(BaseModel):
    """Entrée de patch d’un UserChallenge.

    Attributes:
        status (str | None): Nouveau statut (`pending|accepted|dismissed|completed`).
        notes (str | None): Notes.
        override_reason (str | None): Raison d’override (si `status=completed` manuel).
    """
    status: Optional[str] = Field(default=None, description="pending|accepted|dismissed|completed")
    notes: Optional[str] = None
    override_reason: Optional[str] = Field(default=None, description="Optionnel si status=completed (override manuel)")

class ChallengeMini(BaseModel):
    """Mini-référence challenge.

    Attributes:
        id (PyObjectId): Id du challenge.
        name (str): Nom du challenge.
    """
    id: PyObjectId
    name: str

class ListItem(BaseModel):
    """Élément de liste UC.

    Attributes:
        id (PyObjectId): Id UC.
        status (str): Statut déclaré.
        computed_status (str | None): Statut calculé.
        effective_status (str): Statut effectif.
        progress (dict | None): Snapshot simplifié.
        updated_at (datetime | None): MAJ.
        challenge (ChallengeMini): Réf. challenge.
        cache (CacheDetail): Réf. cache liée.
    """
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    progress: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    challenge: ChallengeMini
    cache: CacheDetail

class ListResponse(BaseModel):
    """Réponse de liste paginée UC.

    Attributes:
        items (list[ListItem]): Résultats.
        page (int): Page courante.
        limit (int): Taille de page.
        total (int): Total.
    """
    items: List[ListItem]
    page: int
    limit: int
    total: int

class CacheDetail(BaseModel):
    """Détail minimal cache.

    Attributes:
        id (PyObjectId): Id cache.
        GC (str): Code GC.
    """
    id: PyObjectId
    GC: str

class ChallengeDetail(BaseModel):
    """Détail minimal challenge.

    Attributes:
        id (PyObjectId): Id challenge.
        name (str): Nom.
        description (str | None): Description.
    """
    id: PyObjectId
    name: str
    description: Optional[str] = None

class DetailResponse(BaseModel):
    """Réponse détail UC.

    Attributes:
        id (PyObjectId): Id UC.
        status (str): Statut déclaré.
        computed_status (str | None): Statut calculé.
        effective_status (str): Statut effectif.
        progress (dict | None): Snapshot simplifié.
        updated_at (datetime | None): MAJ.
        created_at (datetime | None): Création.
        manual_override (bool | None): Override actif.
        override_reason (str | None): Raison.
        overridden_at (datetime | None): Date override.
        notes (str | None): Notes.
        challenge (ChallengeDetail): Détail challenge.
        cache (CacheDetail): Détail cache.
    """
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    progress: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    manual_override: Optional[bool] = None
    override_reason: Optional[str] = None
    overridden_at: Optional[datetime] = None
    notes: Optional[str] = None
    challenge: ChallengeDetail
    cache: CacheDetail


class PatchResponse(BaseModel):
    """Réponse au patch UC.

    Attributes:
        id (PyObjectId): Id UC.
        status (str): Statut déclaré.
        computed_status (str | None): Statut calculé.
        effective_status (str): Statut effectif.
        manual_override (bool | None): Override actif.
        override_reason (str | None): Raison.
        overridden_at (datetime | None): Date override.
        notes (str | None): Notes.
        updated_at (datetime | None): MAJ.
    """
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    manual_override: Optional[bool] = None
    override_reason: Optional[str] = None
    overridden_at: Optional[datetime] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None
