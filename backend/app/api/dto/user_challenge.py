# backend/app/models/user_challenge_dto.py
# I/O schemas for "my challenges" routes (list, detail, patch).

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class PatchUCIn(BaseModel):
    """Patch input for a UserChallenge.

    Attributes:
        status (str | None): New status (`pending|accepted|dismissed|completed`).
        notes (str | None): Notes.
        override_reason (str | None): Override reason (if `status=completed` manual override).
    """

    status: str | None = Field(default=None, description="pending|accepted|dismissed|completed")
    notes: str | None = None
    override_reason: str | None = Field(
        default=None, description="Optional if status=completed (manual override)"
    )


class ChallengeMini(BaseModel):
    """Minimal challenge reference.

    Attributes:
        id (PyObjectId): Challenge id.
        name (str): Challenge name.
    """

    id: PyObjectId
    name: str


class UserChallengeBaseOut(BaseModel):
    """Fields shared by every UserChallenge response shape (list item and detail).

    Attributes:
        id (PyObjectId): UserChallenge id.
        status (str): Declared status.
        computed_status (str | None): Computed status.
        effective_status (str): Effective status.
        progress (dict | None): Simplified snapshot.
        updated_at (datetime | None): Last update.
    """

    id: PyObjectId
    status: str
    computed_status: str | None = None
    effective_status: str
    progress: dict[str, Any] | None = None
    updated_at: datetime | None = None


class UserChallengeListItemOut(UserChallengeBaseOut):
    """UserChallenge list item.

    Attributes:
        challenge (ChallengeMini): Challenge reference.
        cache (CacheDetail): Linked cache reference.
    """

    challenge: ChallengeMini
    cache: CacheDetail


class UserChallengeListResponse(BaseModel):
    """Paginated UserChallenge list response.

    Attributes:
        items (list[UserChallengeListItemOut]): Results.
        nb_items (int): Total items found.
        page (int): Current page.
        nb_pages (int): Total pages.
        page_size (int): Page size.
    """

    items: list[UserChallengeListItemOut]
    nb_items: int
    page: int
    page_size: int
    nb_pages: int


class CacheDetail(BaseModel):
    """Minimal cache detail.

    Attributes:
        id (PyObjectId): Cache id.
        GC (str): GC code.
    """

    id: PyObjectId
    GC: str
    difficulty: float | None = None
    terrain: float | None = None


class ChallengeDetail(BaseModel):
    """Minimal challenge detail.

    Attributes:
        id (PyObjectId): Challenge id.
        name (str): Name.
        description (str | None): Description.
    """

    id: PyObjectId
    name: str
    description: str | None = None


class DetailResponse(UserChallengeBaseOut):
    """UserChallenge detail response.

    Attributes:
        created_at (datetime | None): Creation date.
        manual_override (bool | None): Active override.
        override_reason (str | None): Override reason.
        overridden_at (datetime | None): Override date.
        notes (str | None): Notes.
        challenge (ChallengeDetail): Challenge detail.
        cache (CacheDetail): Cache detail.
    """

    created_at: datetime | None = None
    manual_override: bool | None = None
    override_reason: str | None = None
    overridden_at: datetime | None = None
    notes: str | None = None
    challenge: ChallengeDetail
    cache: CacheDetail


class PatchResponse(BaseModel):
    """UserChallenge patch response.

    Attributes:
        id (PyObjectId): UserChallenge id.
        status (str): Declared status.
        computed_status (str | None): Computed status.
        effective_status (str): Effective status.
        manual_override (bool | None): Active override.
        override_reason (str | None): Override reason.
        overridden_at (datetime | None): Override date.
        notes (str | None): Notes.
        updated_at (datetime | None): Last update.
    """

    id: PyObjectId
    status: str
    computed_status: str | None = None
    effective_status: str
    manual_override: bool | None = None
    override_reason: str | None = None
    overridden_at: datetime | None = None
    notes: str | None = None
    updated_at: datetime | None = None
