
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
    summary="Modifier en lot plusieurs UserChallenges (batch)",
)
def patch_uc_batch(
    items: list[BatchPatchItem] = Body(..., description="Tableau d'items à patcher"),
    current_user: dict = Depends(get_current_user),
):
    """
    Patch en lot :
    - Body = liste d'objets { uc_id, status?, notes?, override_reason? }
    - Réutilise patch_user_challenge() pour chaque item (appartenance user vérifiée côté service).
    - Non transactionnel (best-effort) : on renvoie ok/error par item.
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
