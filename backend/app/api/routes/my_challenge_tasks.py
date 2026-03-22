# backend/app/api/routes/my_challenge_tasks.py
# "My challenge tasks" routes: read, replace (including order), and validate tasks for a UserChallenge.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from app.api.deps import CurrentUserId
from app.api.dto.user_challenge_task import (
    TasksListResponse,
    TasksPutIn,
    TasksValidateIn,
    TasksValidateResponse,
)
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.services.user_challenge_tasks_service import list_tasks, put_tasks, validate_only

router = APIRouter(
    prefix="/my/challenges/{uc_id}/tasks",
    tags=["My challenge tasks"],
    dependencies=[Depends(get_current_user)],
)


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/tasks (GET) to verify
@router.get(
    "",
    response_model=TasksListResponse,
    summary="List the tasks of a UserChallenge",
    description="Returns the **ordered** list of tasks associated with the UserChallenge.",
)
async def get_tasks(
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    user_id: CurrentUserId,
):
    """List the tasks of a UserChallenge.

    Description:
        Retrieves the ordered list of tasks for the user’s challenge.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.

    Returns:
        TasksListResponse: Ordered tasks.
    """
    tasks = await list_tasks(user_id, ObjectId(str(uc_id)))

    return {"tasks": tasks}


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/tasks (PUT) to verify
@router.put(
    "",
    response_model=TasksListResponse,
    summary="Replace all tasks of a UserChallenge",
    description="Replaces **all** tasks (including their order) for the UserChallenge.",
)
async def put_tasks_route(
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    payload: Annotated[
        TasksPutIn, Body(..., description="Complete list of tasks to apply (order included).")
    ],
    user_id: CurrentUserId,
):
    """Replace all tasks (order included).

    Description:
        Overwrites the current task list with the provided new list, preserving order.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.
        payload (TasksPutIn): New tasks (full list).

    Returns:
        TasksListResponse: Tasks persisted after replacement.
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


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/tasks/validate (POST) to verify
@router.post(
    "/validate",
    response_model=TasksValidateResponse,
    summary="Validate a task list (without persisting)",
    description="Validates the consistency of a task list **without saving it**.",
)
async def validate_tasks_route(
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    payload: Annotated[TasksValidateIn, Body(..., description="List of tasks to validate.")],
    user_id: CurrentUserId,
):
    """Validate a task list (without persisting).

    Description:
        Runs consistency checks on the provided task list for the UserChallenge.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.
        payload (TasksValidateIn): Tasks to validate.

    Returns:
        TasksValidateResponse: Validation details (errors, warnings, etc.).
    """
    res = validate_only(
        user_id,
        ObjectId(str(uc_id)),
        [t.model_dump(by_alias=True) for t in payload.tasks],
    )

    return res
