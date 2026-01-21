# backend/app/api/routes/my_challenge_tasks.py
# Routes "mes tâches de challenge" : lire, remplacer (ordre inclus) et valider des tâches pour un UserChallenge.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from app.api.dto.user_challenge_task import (
    TasksListResponse,
    TasksPutIn,
    TasksValidateIn,
    TasksValidateResponse,
)
from app.core.bson_utils import PyObjectId
from app.core.security import CurrentUserId, get_current_user
from app.services.user_challenge_tasks_service import list_tasks, put_tasks, validate_only

router = APIRouter(
    prefix="/my/challenges/{uc_id}/tasks",
    tags=["my-challenge-tasks"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=TasksListResponse,
    summary="Lister les tâches d’un UserChallenge",
    description="Retourne la liste **ordonnée** des tâches associées au UserChallenge.",
)
async def get_tasks(
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    user_id: CurrentUserId,
):
    """Lister les tâches d’un UserChallenge.

    Description:
        Récupère la liste ordonnée des tâches du challenge de l’utilisateur.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.

    Returns:
        TasksListResponse: Tâches ordonnées.
    """
    tasks = await list_tasks(user_id, ObjectId(str(uc_id)))

    return {"tasks": tasks}


@router.put(
    "",
    response_model=TasksListResponse,
    summary="Remplacer toutes les tâches d’un UserChallenge",
    description="Remplace **l’intégralité** des tâches (avec leur ordre) pour le UserChallenge.",
)
async def put_tasks_route(
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    payload: Annotated[
        TasksPutIn, Body(..., description="Liste complète de tâches à appliquer (ordre inclus).")
    ],
    user_id: CurrentUserId,
):
    """Remplacer l’ensemble des tâches (ordre inclus).

    Description:
        Écrase la liste courante des tâches par la nouvelle liste fournie, en respectant l’ordre.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        payload (TasksPutIn): Nouvelles tâches (liste complète).

    Returns:
        TasksListResponse: Tâches persistées après remplacement.
    """
    try:
        tasks = await put_tasks(
            user_id,
            ObjectId(str(uc_id)),
            [t.model_dump(by_alias=True) for t in payload.tasks],
        )
    except ValueError as ve:
        detail = ve.args[0] if ve.args else {"error": "validation"}
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from ve

    return {"tasks": tasks}


@router.post(
    "/validate",
    response_model=TasksValidateResponse,
    summary="Valider une liste de tâches (sans persistance)",
    description="Valide la cohérence d’une liste de tâches **sans l’enregistrer**.",
)
async def validate_tasks_route(
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    payload: Annotated[TasksValidateIn, Body(..., description="Liste de tâches à valider.")],
    user_id: CurrentUserId,
):
    """Valider une liste de tâches (sans persistance).

    Description:
        Exécute les contrôles de cohérence sur la liste de tâches fournie pour le UserChallenge.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        payload (TasksValidateIn): Tâches à valider.

    Returns:
        TasksValidateResponse: Détails de validation (erreurs, avertissements, etc.).
    """
    res = validate_only(
        user_id,
        ObjectId(str(uc_id)),
        [t.model_dump(by_alias=True) for t in payload.tasks],
    )

    return res
