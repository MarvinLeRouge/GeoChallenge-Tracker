# backend/app/models/user_challenge_dto.py
# Schémas I/O pour les routes « mes challenges » (liste, détail, patch).

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class PatchUCIn(BaseModel):
    """Entrée de patch d’un UserChallenge.

    Attributes:
        status (str | None): Nouveau statut (`pending|accepted|dismissed|completed`).
        notes (str | None): Notes.
        override_reason (str | None): Raison d’override (si `status=completed` manuel).
    """

    status: str | None = Field(default=None, description="pending|accepted|dismissed|completed")
    notes: str | None = None
    override_reason: str | None = Field(
        default=None, description="Optionnel si status=completed (override manuel)"
    )


class ChallengeMini(BaseModel):
    """Mini-référence challenge.

    Attributes:
        id (PyObjectId): Id du challenge.
        name (str): Nom du challenge.
    """

    id: PyObjectId
    name: str


class UserChallengeListItemOut(BaseModel):
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
    computed_status: str | None = None
    effective_status: str
    progress: dict[str, Any] | None = None
    updated_at: datetime | None = None
    challenge: ChallengeMini
    cache: CacheDetail


class UserChallengeListResponse(BaseModel):
    """Réponse de liste paginée UC.

    Attributes:
        items (list[UserChallengeListItemOut]): Résultats.
        nb_items (int): Nb items trouvés.
        page (int): Page courante.
        nb_pages (int): Nombre de pages.
        page_size (int): Taille de page.
    """

    items: list[UserChallengeListItemOut]
    nb_items: int
    page: int
    page_size: int
    nb_pages: int


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
    description: str | None = None


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
    computed_status: str | None = None
    effective_status: str
    progress: dict[str, Any] | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None
    manual_override: bool | None = None
    override_reason: str | None = None
    overridden_at: datetime | None = None
    notes: str | None = None
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
    computed_status: str | None = None
    effective_status: str
    manual_override: bool | None = None
    override_reason: str | None = None
    overridden_at: datetime | None = None
    notes: str | None = None
    updated_at: datetime | None = None
