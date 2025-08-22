
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Body, status
from bson import ObjectId

from app.core.security import get_current_user
from app.core.bson_utils import PyObjectId
from app.models.user_challenge_task_dto import (
    TaskIn, TasksPutIn, TasksListResponse, TasksValidateIn, TasksValidateResponse
)
from app.services.user_challenge_tasks import list_tasks, put_tasks, validate_only

router = APIRouter(
    prefix="/my/challenges/{uc_id}/tasks",
    tags=["my-challenge-tasks"],
    dependencies=[Depends(get_current_user)]
)

@router.get("", response_model=TasksListResponse, summary="Lister les tasks (ordonnées) d'un UserChallenge")
def get_tasks(
    uc_id: PyObjectId = Path(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    items = list_tasks(user_id, ObjectId(str(uc_id)))

    return {"items": items}

@router.put("", response_model=TasksListResponse, summary="Remplacer l'ensemble des tasks d'un UserChallenge (ordre inclus)")
def put_tasks_route(
    uc_id: PyObjectId = Path(...),
    payload: TasksPutIn = Body(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    try:
        items = put_tasks(user_id, ObjectId(str(uc_id)), [t.model_dump(by_alias=True) for t in payload.tasks])
    except ValueError as ve:
        detail = ve.args[0] if ve.args else {"error": "validation"}
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    
    return {"items": items}

@router.post("/validate", response_model=TasksValidateResponse, summary="Valider une liste de tasks sans persistance")
def validate_tasks_route(
    uc_id: PyObjectId = Path(...),
    payload: TasksValidateIn = Body(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(str(current_user["_id"]))
    res = validate_only(user_id, ObjectId(str(uc_id)), [t.model_dump(by_alias=True) for t in payload.tasks])
    
    return res
