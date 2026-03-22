# backend/app/api/routes/user_stats.py
# Route to retrieve summary statistics for a user

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUserId
from app.api.dto.user_stats import UserStatsOut
from app.core.security import get_current_user
from app.services.user_stats import get_user_stats

router = APIRouter(
    prefix="/user-stats", tags=["User stats"], dependencies=[Depends(get_current_user)]
)

# --- ROUTES ---------------------------------------------------------------


# DONE: [BACKLOG] Route /user-stats (GET) verified
@router.get(
    "",
    response_model=UserStatsOut,
    status_code=status.HTTP_200_OK,
    summary="Get user statistics",
    description=(
        "Returns summary statistics for the current user "
        "or another user (username as query param, requires admin role).\n\n"
        "**Included metrics:**\n"
        "- Total number of found caches\n"
        "- Number of challenges (total, active, completed)\n"
        "- First/last found cache dates\n"
        "- Account creation date\n"
        "- Last activity (cache or challenge)\n\n"
        "**Access:**\n"
        "- Without parameter: current user's statistics\n"
        "- With `username`: requires admin role"
    ),
)
async def get_user_statistics(
    user_id: CurrentUserId,
    username: Optional[str] = Query(None, description="Target username (admin only)"),
) -> UserStatsOut:
    """Get user statistics.

    Description:
        Computes and returns summary statistics for the current user
        or a specific user (if admin rights).

    Args:
        user_id (CurrentUserId): Current user ID.
        username (str | None): Target username (optional, admin only).

    Returns:
        UserStatsOut: Computed statistics.

    Raises:
        HTTPException 403: If username provided without admin rights.
        HTTPException 404: If target username not found.
        HTTPException 500: If a computation error occurs.
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
