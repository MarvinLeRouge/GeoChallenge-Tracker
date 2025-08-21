
from __future__ import annotations
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from bson import ObjectId

from app.models.target_dto import (
    TargetsPreviewPerTaskResponse,
    TargetsPreviewGlobalResponse,
)
from app.services.targets import (
    preview_targets_for_uc,
    preview_targets_multi_uc,
)
from app.core.security import get_current_user
from app.db.mongodb import get_collection

router = APIRouter()

# --------- per-UC endpoint ---------

@router.get(
    "/my/challenges/{uc_id}/targets/preview",
    response_model=TargetsPreviewPerTaskResponse | TargetsPreviewGlobalResponse,
    tags=["targets"]
)
async def preview_targets_uc(
    uc_id: str = Path(..., description="UserChallenge id"),
    mode: Literal["per_task", "global"] = "per_task",
    k: int = Query(5, ge=1, le=100),
    geo_center: Optional[str] = Query(None, description="lat,lng"),
    geo_radius_km: Optional[float] = Query(None, gt=0),
    bbox: Optional[str] = Query(None, description="minLng,minLat,maxLng,maxLat"),
    max_candidates_pool: int = Query(1000, ge=10, le=10000),
    user = Depends(get_current_user),
):
    # Ensure UC belongs to user
    coll_uc = get_collection("user_challenges")
    uc = coll_uc.find_one({"_id": ObjectId(uc_id), "user_id": ObjectId(user.id)})
    if not uc:
        raise HTTPException(status_code=404, detail="UserChallenge not found")
    return await preview_targets_for_uc(
        user_id=str(user.id),
        uc_id=uc_id,
        mode=mode,
        k=k,
        geo_center=geo_center,
        geo_radius_km=geo_radius_km,
        bbox=bbox,
        max_candidates_pool=max_candidates_pool,
    )

# --------- multi-UC endpoint ---------

@router.get(
    "/my/targets/preview",
    response_model=TargetsPreviewPerTaskResponse | TargetsPreviewGlobalResponse,
    tags=["targets"]
)
async def preview_targets_multi(
    mode: Literal["per_task", "global"] = "global",
    k: int = Query(5, ge=1, le=100),
    geo_center: Optional[str] = Query(None, description="lat,lng"),
    geo_radius_km: Optional[float] = Query(None, gt=0),
    bbox: Optional[str] = Query(None, description="minLng,minLat,maxLng,maxLat"),
    max_candidates_pool: int = Query(1000, ge=10, le=10000),
    user = Depends(get_current_user),
):
    return await preview_targets_multi_uc(
        user_id=str(user.id),
        mode=mode,
        k=k,
        geo_center=geo_center,
        geo_radius_km=geo_radius_km,
        bbox=bbox,
        max_candidates_pool=max_candidates_pool,
    )
