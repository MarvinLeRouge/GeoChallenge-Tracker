# backend/app/api/routes/my_challenge_progress.py
# "My progress" routes: read the latest snapshot + history, and evaluate (immediate or initial) progress on a UserChallenge.

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, CurrentUserId
from app.api.dto.progress import ProgressEvaluateResponse, ProgressGetResponse
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.services.progress import (
    evaluate_new_progress,
    evaluate_progress,
    get_latest_and_history,
)

router = APIRouter(
    prefix="/my/challenges",
    tags=["My challenge progress"],
    dependencies=[Depends(get_current_user)],
)


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/progress (GET) to verify
@router.get(
    "/{uc_id}/progress",
    response_model=ProgressGetResponse,
    summary="Get the latest snapshot and short history",
    description=(
        "Returns the **latest progress snapshot** of a UserChallenge and a **mini-history** (limited).\n\n"
        "- 404 if the UserChallenge does not belong to the user or does not exist\n"
        "- History can be restricted via `before` and `limit`"
    ),
)
async def get_progress_route(
    user_id: CurrentUserId,
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    before: Annotated[
        datetime | None,
        Query(description="Only return history **before** this timestamp."),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=50, description="Number of history entries to return (1–50).")
    ] = 10,
):
    """Retrieve the latest snapshot and short history.

    Description:
        Returns the latest progress snapshot for a given UserChallenge along with a short
        history, paginated by a simple time cursor (`before`) and bounded by `limit`.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.
        limit (int): Maximum number of history entries (1–50).
        before (datetime | None): Time cursor for listing earlier history.

    Returns:
        ProgressGetResponse: Latest snapshot and mini-history.
    """
    out = await get_latest_and_history(user_id, ObjectId(str(uc_id)), limit=limit, before=before)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return out


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/progress/evaluate (POST) to verify
@router.post(
    "/{uc_id}/progress/evaluate",
    response_model=ProgressEvaluateResponse,
    summary="Evaluate and record an immediate snapshot",
    description=(
        "Forces an **immediate evaluation** of progress and **inserts** a new snapshot.\n\n"
        "- The `force` parameter is reserved for administrators\n"
        "- Returns the resulting snapshot"
    ),
)
async def evaluate_progress_route(
    user: CurrentUser,
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    force: bool = Query(
        False,
        description="Force recalculation even if no changes are detected (admin-only).",
    ),
):
    """Evaluate and insert an immediate snapshot.

    Description:
        Triggers a progress recalculation for the target UserChallenge and records a snapshot.
        The `force` option allows bypassing no-change heuristics (reserved for administrators).

    Args:
        uc_id (PyObjectId): UserChallenge identifier.
        force (bool): Force recalculation even without detected changes (admin-only).

    Returns:
        ProgressEvaluateResponse: Evaluated and persisted snapshot.
    """
    if force and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les administrateurs peuvent utiliser le paramètre 'force'",
        )
    if user.id is None:
        raise HTTPException(status_code=400, detail="User ID manquant")

    doc = await evaluate_progress(user_id=user.id, uc_id=ObjectId(str(uc_id)), force=force)
    return doc


class EvaluateNewPayload(BaseModel):
    include_pending: bool = False
    limit: int = 50
    since: datetime | None = None


# TODO: [BACKLOG] Route /my/challenges/new/progress (POST) to verify
@router.post(
    "/new/progress",
    summary="Evaluate the first snapshot for challenges without progress",
    description=(
        "Evaluates a **first snapshot** for **accepted** UserChallenges with no existing progress.\n\n"
        "- `include_pending` option to also include `pending` ones\n"
        "- `limit` and `since` parameters to bound the processing scope"
    ),
)
async def evaluate_new_progress_route(
    payload: Annotated[
        EvaluateNewPayload | None,
        Body(
            description="Initial evaluation options: `include_pending`, `limit`, `since`.",
        ),
    ],
    user_id: CurrentUserId,
):
    """Evaluate the first snapshot for challenges without progress.

    Description:
        Iterates over eligible UserChallenges (by default: `accepted` with no progress) and performs an initial
        evaluation. Can include `pending` ones, and be bounded by volume (`limit`) and date (`since`).

    Args:
        payload (EvaluateNewPayload): Initialization options.

    Returns:
        dict: Statistics and report (created/skipped, etc.).
    """
    if payload is None:
        payload = EvaluateNewPayload()
    res = await evaluate_new_progress(
        user_id,
        include_pending=payload.include_pending,
        limit=payload.limit,
        since=payload.since,
    )
    return res
