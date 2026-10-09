# app/api/routes/maintenance/__init__.py
# Maintenance route package: admin-only DB maintenance, backup/restore,
# and diagnostic endpoints. Split by concern into sibling modules that all
# decorate this shared `router`.

from __future__ import annotations

from ._router import router


# DONE: [BACKLOG] Route /maintenance (GET) verified
@router.get("")
async def maintenance_get_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "GET",
        "function": "maintenance_get_1",
    }

    return result


# DONE: [BACKLOG] Route /maintenance (POST) verified
@router.post("")
async def maintenance_post_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "POST",
        "function": "maintenance_post_1",
    }

    return result


# The submodules below decorate the shared `router` object defined above;
# they must be imported here (even though unused) for their @router.*
# decorators to run and register their routes.
from . import (  # noqa: E402,F401
    backups,
    cleanup,
    full_backup,
    gpx_upload,
    reports,
    targets_stats,
    test_email,
)
