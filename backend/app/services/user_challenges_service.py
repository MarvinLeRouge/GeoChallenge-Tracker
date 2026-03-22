# backend/app/services/user_challenges_service.py
# Compatibility shim for the new UserChallenges system.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.mongodb import get_db

from .user_challenges.user_challenge_service import UserChallengeService

# Global instance for backward compatibility
_user_challenge_service: UserChallengeService | None = None


def get_user_challenge_service() -> UserChallengeService:
    """Return the UserChallenges service instance.

    Returns:
        UserChallengeService: Configured service instance.
    """
    global _user_challenge_service
    if _user_challenge_service is None:
        db = get_db()
        _user_challenge_service = UserChallengeService(db)
    return _user_challenge_service


# Compatibility functions for the legacy API
async def sync_user_challenges(user_id: ObjectId) -> dict[str, int]:
    """Compatibility wrapper — synchronize UserChallenges."""
    service = get_user_challenge_service()
    return await service.sync_user_challenges(user_id)


async def list_user_challenges(
    user_id: ObjectId,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Compatibility wrapper — list UserChallenges."""
    service = get_user_challenge_service()
    return await service.list_user_challenges(
        user_id=user_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


async def get_user_challenge_detail(user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any] | None:
    """Compatibility wrapper — retrieve UC detail."""
    service = get_user_challenge_service()
    return await service.get_user_challenge_detail(user_id, uc_id)


async def patch_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    patch_data: dict[str, Any],
    **kwargs: Any,  # Additional parameters for backward compatibility
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Compatibility wrapper — update a UC."""
    service = get_user_challenge_service()
    return await service.patch_user_challenge(user_id, uc_id, patch_data)
