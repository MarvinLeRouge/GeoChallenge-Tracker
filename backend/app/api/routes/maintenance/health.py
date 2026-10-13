# backend/app/api/routes/maintenance/health.py
# Trivial health-check routes for the maintenance router.

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
