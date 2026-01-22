# backend/app/api/routes/user_stats.py
# Route pour obtenir des statistiques synthétiques sur un utilisateur

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.user_stats import UserStatsOut
from app.core.security import CurrentUserId, get_current_user
from app.services.user_stats import get_user_stats

router = APIRouter(
    prefix="/user-stats", tags=["user_stats"], dependencies=[Depends(get_current_user)]
)

# --- ROUTES ---------------------------------------------------------------


# TODO: [BACKLOG] Route /user-stats (GET) à vérifier
@router.get(
    "",
    response_model=UserStatsOut,
    status_code=status.HTTP_200_OK,
    summary="Obtenir les statistiques d'un utilisateur",
    description=(
        "Retourne les statistiques synthétiques de l'utilisateur courant "
        "ou d'un autre utilisateur (username en query param, nécessite droits admin).\n\n"
        "**Métriques incluses :**\n"
        "- Nombre total de caches trouvées\n"
        "- Nombre de challenges (total, actifs, terminés)\n"
        "- Dates de première/dernière cache trouvée\n"
        "- Date de création du compte\n"
        "- Dernière activité (cache ou challenge)\n\n"
        "**Accès :**\n"
        "- Sans paramètre : statistiques de l'utilisateur courant\n"
        "- Avec `username` : nécessite le rôle admin"
    ),
)
async def get_user_statistics(
    user_id: CurrentUserId,
    username: Optional[str] = Query(
        None, description="Username de l'utilisateur cible (admin seulement)"
    ),
) -> UserStatsOut:
    """Obtenir les statistiques d'un utilisateur.

    Description:
        Calcule et retourne les statistiques synthétiques pour l'utilisateur courant
        ou un utilisateur spécifique (si droits admin).

    Args:
        user_id (CurrentUserId): ID de l'utilisateur courant.
        username (str | None): Username cible (optionnel, admin seulement).

    Returns:
        UserStatsOut: Statistiques calculées.

    Raises:
        HTTPException 403: Si username fourni sans droits admin.
        HTTPException 404: Si username cible non trouvé.
        HTTPException 500: Si erreur de calcul.
    """
    try:
        stats = await get_user_stats(user_id, username)
        return stats

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating user statistics: {str(e)}",
        ) from e
