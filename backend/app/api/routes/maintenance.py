# app/api/routes/maintenance.py

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_admin

router = APIRouter(
    prefix="/maintenance", tags=["maintenance"], dependencies=[Depends(require_admin)]
)


@router.get("")
def maintenance_get_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "GET",
        "function": "maintenance_get_1",
    }

    return result


@router.post("")
def maintenance_post_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "POST",
        "function": "maintenance_post_1",
    }

    return result
