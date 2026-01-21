# backend/app/services/user_challenge_tasks_service.py
# Fichier de compatibilité pour le nouveau système de tâches UserChallenge

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.domain.models.challenge_ast import TaskExpression

from .user_challenge_tasks.user_challenge_task_service import UserChallengeTaskService

# Instance globale pour compatibilité
_user_challenge_task_service: UserChallengeTaskService | None = None


def get_user_challenge_task_service() -> UserChallengeTaskService:
    """Obtenir l'instance du service de tâches UserChallenge.

    Returns:
        UserChallengeTaskService: Instance configurée du service.
    """
    global _user_challenge_task_service
    if _user_challenge_task_service is None:
        _user_challenge_task_service = UserChallengeTaskService()
    return _user_challenge_task_service


# === FONCTIONS DE COMPATIBILITÉ EXACTES ===


async def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> list[dict[str, Any]]:
    """Fonction de compatibilité - lister les tâches d'un UC.

    SIGNATURE IDENTIQUE À L'ORIGINALE.
    """
    service = get_user_challenge_task_service()
    return await service.list_tasks(user_id, uc_id)


def validate_only(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fonction de compatibilité - valider sans persister.

    SIGNATURE IDENTIQUE À L'ORIGINALE.
    """
    service = get_user_challenge_task_service()
    return service.validate_only(user_id, uc_id, tasks_payload)


async def put_tasks(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fonction de compatibilité - remplacer toutes les tâches.

    SIGNATURE IDENTIQUE À L'ORIGINALE.
    """
    service = get_user_challenge_task_service()
    return await service.put_tasks(user_id, uc_id, tasks_payload)


def compile_expression_to_cache_match(expr: TaskExpression) -> dict[str, Any]:
    """Fonction de compatibilité - compiler AST vers filtre MongoDB.

    SIGNATURE IDENTIQUE À L'ORIGINALE.
    """
    service = get_user_challenge_task_service()
    return service.compile_expression_to_cache_match(expr)


def validate_task_expression(expr: TaskExpression) -> list[str]:
    """Fonction de compatibilité - valider une expression AST.

    SIGNATURE IDENTIQUE À L'ORIGINALE.
    """
    service = get_user_challenge_task_service()
    return service.validate_task_expression(expr)
