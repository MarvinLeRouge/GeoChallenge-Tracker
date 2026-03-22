# backend/app/api/routes/challenges.py
# Admin routes to automatically (re)create challenges from "challenge" caches.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.services.challenge_autocreate import create_challenges_from_caches

router = APIRouter(
    prefix="/challenges", tags=["Challenges"], dependencies=[Depends(get_current_user)]
)


class RefreshIn(BaseModel):
    cache_ids: list[PyObjectId] | None = Field(
        default=None,
        description="Optional list of cache_ids (Mongo _id) to consider; if absent, scans the entire collection.",
    )


# TODO: [BACKLOG] Route /challenges/refresh-from-caches (POST) to verify
@router.post(
    "/refresh-from-caches",
    summary="(Re)create challenges from ‘challenge’ caches",
    description=(
        "Scans caches marked as ‘challenge’ and creates/updates challenge documents.\n\n"
        "- Option: restrict to a list of `cache_ids`\n"
        "- Reserved for administrators (`require_admin` dependency)"
    ),
    dependencies=[Depends(require_admin)],
)
async def refresh_from_caches(
    payload: Annotated[
        RefreshIn,
        Body(
            default_factory=RefreshIn,
            description="Execution parameters: optionally a list of `cache_ids` (Mongo _id) to process.",
        ),
    ],
):
    """(Re)create challenges from caches.

    Description:
        Triggers generation/refresh of challenges from caches marked as ‘challenge’
        (e.g. via a specific attribute). Can be restricted to specific caches.

    Args:
        payload (RefreshIn): Optional list of MongoDB `cache_ids` to process.

    Returns:
        dict: Success indicator and processing statistics.
    """
    cache_ids = None
    if payload.cache_ids:
        cache_ids = [ObjectId(str(x)) for x in payload.cache_ids]
    stats = await create_challenges_from_caches(cache_ids=cache_ids)

    return {"ok": True, "stats": stats}
