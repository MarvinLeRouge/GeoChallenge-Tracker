# backend/app/api/deps.py
# Shared FastAPI dependencies used across routes.

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user, get_current_user_id
from app.domain.models.user import User

# Type aliases for handler injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserId = Annotated[PyObjectId, Depends(get_current_user_id)]


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """FastAPI dependency: verifies that the current user is an administrator.

    Args:
        current_user (User): Authenticated user (injected via get_current_user).

    Returns:
        User: The user if their role is 'admin'.

    Raises:
        HTTPException: 403 if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user
