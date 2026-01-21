# backend/app/api/routes/my_challenge_progress.py
# Routes "mon avancée" : lecture du dernier snapshot + historique, et évaluation (immédiate ou initiale) du progrès sur un UserChallenge.

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from app.api.dto.progress import ProgressEvaluateResponse, ProgressGetResponse
from app.core.bson_utils import PyObjectId
from app.core.security import CurrentUser, CurrentUserId, get_current_user
from app.services.progress import (
    evaluate_new_progress,
    evaluate_progress,
    get_latest_and_history,
)

router = APIRouter(
    prefix="/my/challenges",
    tags=["my-challenge-progress"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/{uc_id}/progress",
    response_model=ProgressGetResponse,
    summary="Obtenir le dernier snapshot et l’historique court",
    description=(
        "Retourne le **dernier snapshot** de progression d’un UserChallenge et un **mini-historique** (limité).\n\n"
        "- 404 si le UserChallenge n’appartient pas à l’utilisateur ou n’existe pas\n"
        "- L’historique peut être restreint via `before` et `limit`"
    ),
)
async def get_progress_route(
    user_id: CurrentUserId,
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    before: Annotated[
        datetime | None,
        Query(description="Ne renvoyer que l’historique **antérieur** à ce timestamp."),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=50, description="Nombre d’entrées d’historique à renvoyer (1–50).")
    ] = 10,
):
    """Récupérer le dernier snapshot et l’historique court.

    Description:
        Cette route retourne le dernier snapshot de progression pour un UserChallenge donné ainsi qu’un
        historique court, paginé par un simple curseur temporel (`before`) et limité par `limit`.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        limit (int): Nombre maximal d’entrées d’historique (1–50).
        before (datetime | None): Curseur temporel pour lister l’historique antérieur.

    Returns:
        ProgressGetResponse: Dernier snapshot et mini-historique.
    """
    out = get_latest_and_history(user_id, ObjectId(str(uc_id)), limit=limit, before=before)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return out


@router.post(
    "/{uc_id}/progress/evaluate",
    response_model=ProgressEvaluateResponse,
    summary="Évaluer et enregistrer un snapshot immédiat",
    description=(
        "Force une **évaluation immédiate** de la progression et **insère** un nouveau snapshot.\n\n"
        "- Paramètre `force` réservé aux administrateurs\n"
        "- Retourne le snapshot résultant"
    ),
)
async def evaluate_progress_route(
    user: CurrentUser,
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    force: bool = Query(
        False,
        description="Forcer le recalcul même si aucun changement détecté (admin-only).",
    ),
):
    """Évaluer et insérer un snapshot immédiat.

    Description:
        Déclenche un recalcul de la progression pour le UserChallenge visé et enregistre un snapshot.
        L’option `force` permet d’ignorer les heuristiques de non-changement (réservé aux administrateurs).

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        force (bool): Forcer le recalcul même sans changement détecté (admin-only).

    Returns:
        ProgressEvaluateResponse: Snapshot évalué et persisté.
    """
    if force and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les administrateurs peuvent utiliser le paramètre 'force'",
        )
    if user.id is None:
        raise HTTPException(status_code=400, detail="User ID manquant")

    doc = evaluate_progress(user_id=user.id, uc_id=ObjectId(str(uc_id)), force=force)
    return doc


class EvaluateNewPayload(BaseModel):
    include_pending: bool = False
    limit: int = 50
    since: datetime | None = None


@router.post(
    "/new/progress",
    summary="Évaluer le premier snapshot pour les challenges sans progression",
    description=(
        "Évalue un **premier snapshot** pour les UserChallenges **acceptés** sans progression existante.\n\n"
        "- Option `include_pending` pour inclure les `pending`\n"
        "- Paramètres `limit` et `since` pour borner le traitement"
    ),
)
async def evaluate_new_progress_route(
    payload: Annotated[
        EvaluateNewPayload | None,
        Body(
            description="Options d’évaluation initiale : `include_pending`, `limit`, `since`.",
        ),
    ],
    user_id: CurrentUserId,
):
    """Évaluer le premier snapshot pour les challenges sans progression.

    Description:
        Parcourt les UserChallenges éligibles (par défaut: `accepted` sans progression) et effectue une première
        évaluation. Peut inclure les `pending`, être borné en volume (`limit`) et en date (`since`).

    Args:
        payload (EvaluateNewPayload): Options d’initialisation.

    Returns:
        dict: Statistiques et compte-rendu (créés/ignorés, etc.).
    """
    if payload is None:
        payload = EvaluateNewPayload()
    res = evaluate_new_progress(
        user_id,
        include_pending=payload.include_pending,
        limit=payload.limit,
        since=payload.since,
    )
    return res
