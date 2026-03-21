# backend/app/api/deps.py
# Dépendances FastAPI partagées entre les routes.

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user, get_current_user_id
from app.domain.models.user import User

# Type aliases pour injection dans les handlers
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserId = Annotated[PyObjectId, Depends(get_current_user_id)]


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Dépendance FastAPI : vérifie que l'utilisateur courant est administrateur.

    Args:
        current_user (User): Utilisateur authentifié (injecté via get_current_user).

    Returns:
        User: L'utilisateur si son rôle est 'admin'.

    Raises:
        HTTPException: 403 si l'utilisateur n'est pas admin.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user
