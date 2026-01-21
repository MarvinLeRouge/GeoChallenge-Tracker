# backend/app/services/user_challenges_service.py
# Fichier de compatibilité pour le nouveau système de UserChallenges.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.mongodb import db

from .user_challenges.user_challenge_service import UserChallengeService

# Instance globale pour compatibilité
_user_challenge_service: UserChallengeService | None = None


def get_user_challenge_service() -> UserChallengeService:
    """Obtenir l'instance du service UserChallenges.

    Returns:
        UserChallengeService: Instance configurée du service.
    """
    global _user_challenge_service
    if _user_challenge_service is None:
        _user_challenge_service = UserChallengeService(db)
    return _user_challenge_service


# Fonctions de compatibilité pour l'ancien API
async def sync_user_challenges(user_id: ObjectId) -> dict[str, int]:
    """Fonction de compatibilité - synchroniser les UserChallenges."""
    service = get_user_challenge_service()
    return await service.sync_user_challenges(user_id)


async def list_user_challenges(
    user_id: ObjectId,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Fonction de compatibilité - lister les UserChallenges."""
    service = get_user_challenge_service()
    return await service.list_user_challenges(
        user_id=user_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


async def get_user_challenge_detail(user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any] | None:
    """Fonction de compatibilité - récupérer le détail d'un UC."""
    service = get_user_challenge_service()
    return await service.get_user_challenge_detail(user_id, uc_id)


async def patch_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    patch_data: dict[str, Any],
    **kwargs: Any,  # Paramètres additionnels pour compatibilité
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Fonction de compatibilité - mettre à jour un UC."""
    service = get_user_challenge_service()
    return await service.patch_user_challenge(user_id, uc_id, patch_data)
