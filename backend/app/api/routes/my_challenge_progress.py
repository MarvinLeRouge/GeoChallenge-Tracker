from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from bson import ObjectId

from app.core.security import get_current_user
from app.core.bson_utils import PyObjectId
from app.models.progress_dto import (
    ProgressGetResponse, ProgressEvaluateResponse
)
from app.services.progress import (
    get_latest_and_history, evaluate_progress, evaluate_new_progress
)

router = APIRouter(
    prefix="/my/challenges",
    tags=["my-challenge-progress"],
)

@router.get("/{uc_id}/progress", response_model=ProgressGetResponse, summary="Dernier snapshot + mini-historique")
def get_progress_route(
    uc_id: PyObjectId = Path(...),
    limit: int = Query(10, ge=1, le=50),
    before: Optional[datetime] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    out = get_latest_and_history(user_id, ObjectId(str(uc_id)), limit=limit, before=before)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return out

@router.post("/{uc_id}/progress/evaluate", response_model=ProgressEvaluateResponse, summary="Évaluer et insérer un snapshot immédiat")
def evaluate_progress_route(
    uc_id: PyObjectId = Path(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    doc = evaluate_progress(user_id, ObjectId(str(uc_id)))
    return doc

class EvaluateNewPayload(BaseModel):
    include_pending: bool = False
    limit: int = 50
    since: Optional[datetime] = None

@router.post("/new/progress", summary="Évaluer le premier snapshot pour les challenges acceptés sans progress")
def evaluate_new_progress_route(
    payload: EvaluateNewPayload = Body(default=EvaluateNewPayload()),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    res = evaluate_new_progress(
        user_id,
        include_pending=payload.include_pending,
        limit=payload.limit,
        since=payload.since,
    )
    return res
