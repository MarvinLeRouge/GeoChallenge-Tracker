
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from pydantic import BaseModel, Field
from datetime import datetime

from bson import ObjectId
from app.core.security import get_current_user
from app.core.bson_utils import PyObjectId

from app.models.user_challenge_dto import (
    ListResponse,
    DetailResponse,
    PatchUCIn,
    PatchResponse,
)

from app.services.user_challenges import (
    sync_user_challenges,
    list_user_challenges,
    patch_user_challenge,
    get_user_challenge_detail,
)

router = APIRouter(
    prefix="/my/challenges",
    tags=["my-challenges"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/sync", summary="Créer les UserChallenges manquants (status=pending)", status_code=200)
def sync(current_user: dict = Depends(get_current_user)):
    user_id = ObjectId(str(current_user["_id"]))
    stats = sync_user_challenges(user_id)
    return stats

@router.get("", response_model=ListResponse, summary="Lister mes challenges")
def list_uc(
    status: Optional[str] = Query(default=None, enum=["pending", "accepted", "dismissed", "completed"]),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    return list_user_challenges(user_id, status, page, limit)

@router.patch("/{uc_id}", response_model=PatchResponse, summary="Modifier le statut/notes d'un UserChallenge")
def patch_uc(
    uc_id: PyObjectId = Path(...),
    payload: PatchUCIn = Body(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    doc = patch_user_challenge(
        user_id=user_id,
        uc_id=ObjectId(str(uc_id)),
        status=payload.status,
        notes=payload.notes,
        override_reason=payload.override_reason,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc

@router.get("/{uc_id}", response_model=DetailResponse, summary="Détail d'un UserChallenge")
def get_uc(
    uc_id: PyObjectId = Path(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    doc = get_user_challenge_detail(user_id, ObjectId(str(uc_id)))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc
