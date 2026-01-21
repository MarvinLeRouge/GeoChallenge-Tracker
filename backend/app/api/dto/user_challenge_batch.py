from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class BatchPatchItem(BaseModel):
    """Item for batch patching UserChallenges."""

    uc_id: PyObjectId = Field(..., description="UserChallenge id")
    status: str | None = Field(
        default=None,
        description="Nouveau statut (pending|accepted|dismissed|completed)",
    )
    notes: str | None = None
    override_reason: str | None = None


class BatchPatchResultItem(BaseModel):
    """Result item for batch patching."""

    uc_id: PyObjectId
    ok: bool
    error: str | None = None


class BatchPatchResponse(BaseModel):
    """Response for batch patching UserChallenges."""

    updated_count: int
    total: int
    results: list[BatchPatchResultItem]
