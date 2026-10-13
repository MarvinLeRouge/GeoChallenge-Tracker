# backend/app/api/router_registry.py
# Assembles every API router for inclusion in the FastAPI app.
#
# Lives above app.api.routes (and app.api.routes.maintenance) specifically so
# that neither package needs to import its own submodules for side effects:
# modules sharing one router object across siblings (caches_search/
# caches_geo_search/caches_lookup decorating .caches's router, and the
# maintenance submodules decorating .maintenance's router) are wired here
# instead. A package's own __init__ importing its own children creates a
# circular dependency at the package level (the parent needs the child to
# register routes, the child needs the parent initialized to resolve its
# relative imports); doing that wiring in a module outside both packages
# breaks the cycle.

from __future__ import annotations

# caches_search/caches_geo_search/caches_lookup decorate the same shared
# `caches_router` object (imported from .caches); they must be imported here,
# even though unused, for their @router.* decorators to run and register
# their routes.
from app.api.routes import caches_geo_search, caches_lookup, caches_search  # noqa: F401
from app.api.routes.admin_geo import router as admin_geo_router
from app.api.routes.auth import router as auth_router
from app.api.routes.caches import router as caches_router
from app.api.routes.caches_elevation import router as caches_elevation_router
from app.api.routes.caches_geocoding import router as caches_geocoding_router
from app.api.routes.challenges import router as challenges_router

# backups/cleanup/full_backup/gpx_upload/health/reports/targets_stats/test_email
# decorate the same shared `router` object (defined in .maintenance._router);
# they must be imported here, even though unused, for their @router.*
# decorators to run and register their routes.
from app.api.routes.maintenance import (  # noqa: F401
    backups,
    cleanup,
    full_backup,
    gpx_upload,
    health,
    reports,
    targets_stats,
    test_email,
)
from app.api.routes.maintenance._router import router as maintenance_router
from app.api.routes.meta import router as health_router
from app.api.routes.my_challenge_progress import router as my_challenge_progress_router
from app.api.routes.my_challenge_targets import router as my_challenge_targets_router
from app.api.routes.my_challenge_tasks import router as my_challenge_tasks_router
from app.api.routes.my_challenges import router as my_challenges_router
from app.api.routes.my_profile import router as my_profile_router
from app.api.routes.referentials import router as referentials_router
from app.api.routes.zones import router as zones_router

routers = [
    health_router,
    referentials_router,
    auth_router,
    admin_geo_router,
    caches_router,
    caches_elevation_router,
    caches_geocoding_router,
    challenges_router,
    my_challenges_router,
    my_challenge_tasks_router,
    my_challenge_progress_router,
    my_challenge_targets_router,
    my_profile_router,
    maintenance_router,
    zones_router,
]
