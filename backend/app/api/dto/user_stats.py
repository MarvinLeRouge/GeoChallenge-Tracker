# backend/app/models/user_stats_dto.py
# DTOs pour les statistiques utilisateur

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class CacheTypeStats(BaseModel):
    """Statistiques pour un type de cache spécifique.

    Attributes:
        type_id (PyObjectId): Identifiant du type de cache.
        type_label (str): Libellé du type de cache.
        type_code (str): Code du type de cache.
        count (int): Nombre de caches trouvées de ce type.
    """

    type_id: PyObjectId
    type_label: str
    type_code: str
    count: int = Field(ge=0, description="Nombre de caches trouvées de ce type")


class UserStatsOut(BaseModel):
    """Statistiques synthétiques d'un utilisateur.

    Attributes:
        user_id (PyObjectId): Identifiant utilisateur.
        username (str): Nom d'utilisateur.
        total_caches_found (int): Nombre total de caches trouvées.
        total_challenges (int): Nombre total de challenges.
        active_challenges (int): Nombre de challenges actifs (accepted).
        completed_challenges (int): Nombre de challenges terminés.
        first_cache_found_at (datetime | None): Date de la première cache trouvée.
        last_cache_found_at (datetime | None): Date de la dernière cache trouvée.
        created_at (datetime): Date de création du compte.
        last_activity_at (datetime | None): Dernière activité (cache trouvée ou challenge créé).
        cache_types_stats (list[CacheTypeStats] | None): Statistiques par type de cache.
    """

    user_id: PyObjectId
    username: str
    total_caches_found: int = Field(ge=0, description="Nombre total de caches trouvées")
    total_challenges: int = Field(ge=0, description="Nombre total de challenges")
    active_challenges: int = Field(ge=0, description="Challenges actifs (accepted)")
    completed_challenges: int = Field(ge=0, description="Challenges terminés")
    first_cache_found_at: Optional[datetime] = Field(
        None, description="Date de la première cache trouvée"
    )
    last_cache_found_at: Optional[datetime] = Field(
        None, description="Date de la dernière cache trouvée"
    )
    created_at: datetime = Field(description="Date de création du compte")
    last_activity_at: Optional[datetime] = Field(None, description="Dernière activité")
    cache_types_stats: Optional[list[CacheTypeStats]] = Field(
        None, description="Statistiques par type de cache"
    )
