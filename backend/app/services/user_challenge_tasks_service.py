# backend/app/services/user_challenge_tasks_service.py
# Compatibility shim for the new UserChallenge task system.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.domain.models.challenge_ast import TaskExpression

from .user_challenge_tasks.user_challenge_task_service import UserChallengeTaskService

# Global instance for backward compatibility
_user_challenge_task_service: UserChallengeTaskService | None = None


def get_user_challenge_task_service() -> UserChallengeTaskService:
    """Return the UserChallenge task service instance.

    Returns:
        UserChallengeTaskService: Configured service instance.
    """
    global _user_challenge_task_service
    if _user_challenge_task_service is None:
        _user_challenge_task_service = UserChallengeTaskService()
    return _user_challenge_task_service


# === EXACT COMPATIBILITY FUNCTIONS ===


async def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> list[dict[str, Any]]:
    """Compatibility wrapper — list tasks for a UC.

    SIGNATURE IDENTICAL TO THE ORIGINAL.
    """
    service = get_user_challenge_task_service()
    return await service.list_tasks(user_id, uc_id)


def validate_only(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compatibility wrapper — validate without persisting.

    SIGNATURE IDENTICAL TO THE ORIGINAL.
    """
    service = get_user_challenge_task_service()
    return service.validate_only(user_id, uc_id, tasks_payload)


async def put_tasks(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compatibility wrapper — replace all tasks.

    SIGNATURE IDENTICAL TO THE ORIGINAL.
    """
    service = get_user_challenge_task_service()
    return await service.put_tasks(user_id, uc_id, tasks_payload)


def compile_expression_to_cache_match(expr: TaskExpression) -> dict[str, Any]:
    """Compatibility wrapper — compile AST to MongoDB filter.

    SIGNATURE IDENTICAL TO THE ORIGINAL.
    """
    service = get_user_challenge_task_service()
    return service.compile_expression_to_cache_match(expr)


def validate_task_expression(expr: TaskExpression) -> list[str]:
    """Compatibility wrapper — validate an AST expression.

    SIGNATURE IDENTICAL TO THE ORIGINAL.
    """
    service = get_user_challenge_task_service()
    return service.validate_task_expression(expr)
