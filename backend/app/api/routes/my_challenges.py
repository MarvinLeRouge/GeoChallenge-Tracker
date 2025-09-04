# backend/app/api/routes/my_challenges.py
# Routes "mes challenges" : synchronisation, listing, patch en lot, détail et patch unitaire d’un UserChallenge.

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

@router.post(
    "/sync",
    status_code=200,
    summary="Synchroniser les UserChallenges manquants",
    description=(
        "Crée les UserChallenges **manquants** pour l’utilisateur courant (statut `pending`).\n\n"
        "- N’altère pas ceux déjà existants\n"
        "- Retourne des statistiques de synchronisation"
    ),
)
def sync(
    current_user: dict = Depends(get_current_user),
):
    """Synchroniser les UserChallenges.

    Description:
        Crée les UserChallenges manquants (status initial `pending`) en fonction des challenges disponibles.

    Args:
        current_user (dict): Contexte utilisateur.

    Returns:
        dict: Statistiques (créations, ignorés, etc.).
    """
    user_id = ObjectId(str(current_user["_id"]))
    stats = sync_user_challenges(user_id)
    return stats

@router.get(
    "",
    response_model=ListResponse,
    summary="Lister mes UserChallenges",
    description=(
        "Retourne la liste paginée des UserChallenges de l’utilisateur.\n\n"
        "- Filtre optionnel `status` (pending|accepted|dismissed|completed)\n"
        "- Pagination via `page` et `limit` (max 200)"
    ),
)
def list_uc(
    status: Optional[str] = Query(
        default=None,
        enum=["pending", "accepted", "dismissed", "completed"],
        description="Filtrer par statut du UserChallenge.",
    ),
    page: int = Query(1, ge=1, description="Numéro de page (≥1)."),
    limit: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
    current_user: dict = Depends(get_current_user),
):
    """Lister mes UserChallenges (paginé).

    Description:
        Permet de filtrer par statut et de paginer la liste des UserChallenges.

    Args:
        status (str | None): Statut à filtrer.
        page (int): Numéro de page (≥1).
        limit (int): Taille de page (1–200).
        current_user (dict): Contexte utilisateur.

    Returns:
        ListResponse: Items et informations de pagination.
    """
    user_id = ObjectId(str(current_user["_id"]))
    return list_user_challenges(user_id, status, page, limit)

# --- modèles locaux pour le batch ---
class BatchPatchItem(BaseModel):
    uc_id: PyObjectId = Field(..., description="UserChallenge id")
    status: Optional[str] = Field(default=None, description="Nouveau statut (pending|accepted|dismissed|completed)")
    notes: Optional[str] = None
    override_reason: Optional[str] = None

class BatchPatchResultItem(BaseModel):
    uc_id: PyObjectId
    ok: bool
    error: Optional[str] = None

class BatchPatchResponse(BaseModel):
    updated_count: int
    total: int
    results: list[BatchPatchResultItem]


@router.patch(
    "",
    response_model=BatchPatchResponse,
    summary="Patch en lot de plusieurs UserChallenges",
    description=(
        "Modifie en **lot** le statut/notes/override_reason de plusieurs UserChallenges.\n\n"
        "- Non transactionnel (best-effort)\n"
        "- Max 200 items"
    ),
)
def patch_uc_batch(
    items: list[BatchPatchItem] = Body(..., description="Tableau d’ordres de patch (uc_id, status?, notes?, override_reason?)."),
    current_user: dict = Depends(get_current_user),
):
    """Patch en lot de UserChallenges.

    Description:
        Applique des mises à jour itemisées sur plusieurs UserChallenges. Chaque item est validé et produit un résultat
        distinct (succès/erreur), sans échec global si un item échoue.

    Args:
        items (list[BatchPatchItem]): Liste d’ordres de patch.
        current_user (dict): Contexte utilisateur.

    Returns:
        BatchPatchResponse: Résultats détaillés par item et nombre de mises à jour.
    """
    if not items:
        return BatchPatchResponse(updated_count=0, total=0, results=[])

    # garde-fou
    if len(items) > 200:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="Batch trop volumineux (max 200 items)")

    user_id = ObjectId(str(current_user["_id"]))

    results: list[BatchPatchResultItem] = []
    updated = 0

    for it in items:
        try:
            doc = patch_user_challenge(
                user_id=user_id,
                uc_id=ObjectId(str(it.uc_id)),
                status=it.status,
                notes=it.notes,
                override_reason=it.override_reason,
            )
            if not doc:
                results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error="UserChallenge not found"))
                continue
            updated += 1
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=True))
        except HTTPException as e:
            # propage les 404 du service en résultat itemisé plutôt qu’en échec global
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e.detail)))
        except Exception as e:
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e)))

    return BatchPatchResponse(updated_count=updated, total=len(items), results=results)

@router.get(
    "/{uc_id}",
    response_model=DetailResponse,
    summary="Détail d’un UserChallenge",
    description="Retourne le détail d’un UserChallenge appartenant à l’utilisateur.",
)
def get_uc(
    uc_id: PyObjectId = Path(..., description="Identifiant du UserChallenge."),
    current_user: dict = Depends(get_current_user),
):
    """Détail d’un UserChallenge.

    Description:
        Récupère le UserChallenge s’il appartient à l’utilisateur courant, sinon renvoie 404.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        current_user (dict): Contexte utilisateur.

    Returns:
        DetailResponse: Détail du UserChallenge.
    """
    user_id = ObjectId(str(current_user["_id"]))
    doc = get_user_challenge_detail(user_id, ObjectId(str(uc_id)))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc

@router.patch(
    "/{uc_id}",
    response_model=PatchResponse,
    summary="Modifier statut/notes d’un UserChallenge",
    description=(
        "Met à jour un UserChallenge : statut (`pending|accepted|dismissed|completed`), notes et `override_reason`."
    ),
)
def patch_uc(
    uc_id: PyObjectId = Path(..., description="Identifiant du UserChallenge."),
    payload: PatchUCIn = Body(..., description="Champs modifiables : `status`, `notes`, `override_reason`."),
    current_user: dict = Depends(get_current_user),
):
    """Patch d’un UserChallenge.

    Description:
        Met à jour le statut et/ou les notes (et le `override_reason`) d’un UserChallenge appartenant à l’utilisateur.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        payload (PatchUCIn): Données de mise à jour.
        current_user (dict): Contexte utilisateur.

    Returns:
        PatchResponse: UserChallenge après mise à jour.
    """
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

