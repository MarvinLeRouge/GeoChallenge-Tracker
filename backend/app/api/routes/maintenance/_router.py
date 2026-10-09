"""Shared router for maintenance endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import require_admin

router = APIRouter(
    prefix="/maintenance",
    tags=["Maintenance"],
    dependencies=[Depends(require_admin)],
)
