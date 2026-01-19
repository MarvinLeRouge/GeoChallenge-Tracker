# backend/app/api/routes/__init__.py
# Point d’entrée : regroupe tous les routeurs de l’API pour inclusion dans FastAPI.

from .auth import router as auth_router
from .base import router as base_router
from .caches import router as caches_router
from .caches_elevation import router as caches_elevation_router
from .challenges import router as challenges_router
from .maintenance import router as maintenance_router
from .my_challenge_progress import router as my_challenge_progress_router
from .my_challenge_targets import router as my_challenge_targets_router
from .my_challenge_tasks import router as my_challenge_tasks_router
from .my_challenges import router as my_challenges_router
from .my_profile import router as my_profile_router
from .user_stats import router as user_stats_router

routers = [
    base_router,
    auth_router,
    caches_router,
    caches_elevation_router,
    challenges_router,
    my_challenges_router,
    my_challenge_tasks_router,
    my_challenge_progress_router,
    my_challenge_targets_router,
    my_profile_router,
    user_stats_router,
    maintenance_router,
]
