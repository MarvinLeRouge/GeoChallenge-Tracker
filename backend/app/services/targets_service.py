# backend/app/services/targets_service.py
# Fichier de compatibilité et point d'entrée principal pour le nouveau système de targets.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.mongodb import db

from .targets.target_service import TargetService

# Instance globale pour compatibilité avec l'ancien système
_target_service: TargetService | None = None


def get_target_service() -> TargetService:
    """Obtenir l'instance du service de targets.

    Returns:
        TargetService: Instance configurée du service.
    """
    global _target_service
    if _target_service is None:
        _target_service = TargetService(db)
    return _target_service


# Fonctions de compatibilité pour l'ancien API
async def evaluate_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit_per_task: int = 200,
    hard_limit_total: int = 2000,
    geo_ctx: dict[str, Any] | None = None,
    evaluated_at: Any = None,
    force: bool = False,
) -> dict[str, Any]:
    """Fonction de compatibilité - évaluer les targets d'un UserChallenge."""
    service = get_target_service()
    return await service.evaluate_targets_for_user_challenge(
        user_id=user_id,
        uc_id=uc_id,
        limit_per_task=limit_per_task,
        hard_limit_total=hard_limit_total,
        geo_ctx=geo_ctx,
        evaluated_at=evaluated_at,
        force=force,
    )


async def list_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    page: int = 1,
    page_size: int = 50,
    sort: str = "-score",
) -> dict[str, Any]:
    """Fonction de compatibilité - lister les targets d'un UC."""
    service = get_target_service()
    return await service.list_targets_for_user_challenge(
        user_id=user_id,
        uc_id=uc_id,
        page=page,
        page_size=page_size,
        sort=sort,
    )


async def list_targets_nearby_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    page: int = 1,
    page_size: int = 50,
    sort: str = "distance",
) -> dict[str, Any]:
    """Fonction de compatibilité - lister les targets proches d'un UC."""
    service = get_target_service()
    return await service.list_targets_nearby_for_user_challenge(
        user_id=user_id,
        uc_id=uc_id,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        page=page,
        page_size=page_size,
        sort=sort,
    )


async def list_targets_for_user(
    user_id: ObjectId,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "-score",
) -> dict[str, Any]:
    """Fonction de compatibilité - lister toutes les targets d'un utilisateur."""
    service = get_target_service()
    return await service.list_targets_for_user(
        user_id=user_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        sort=sort,
    )


async def list_targets_nearby_for_user(
    user_id: ObjectId,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 50.0,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "distance",
) -> dict[str, Any]:
    """Fonction de compatibilité - lister les targets proches pour un utilisateur."""
    service = get_target_service()
    return await service.list_targets_nearby_for_user(
        user_id=user_id,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        sort=sort,
    )


async def delete_targets_for_user_challenge(user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any]:
    """Fonction de compatibilité - supprimer les targets d'un UC."""
    service = get_target_service()
    return await service.delete_targets_for_user_challenge(user_id=user_id, uc_id=uc_id)
