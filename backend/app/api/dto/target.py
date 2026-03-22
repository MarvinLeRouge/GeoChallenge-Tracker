# backend/app/models/target_dto.py
# Output schemas for target endpoints (lists, per-task, global).

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---- Common types ----


class LocOut(BaseModel):
    """Decimal coordinates.

    Attributes:
        lat (float): Latitude.
        lng (float): Longitude.
    """

    lat: float
    lng: float


# ---- List outputs for GET /targets routes ----


class TargetListItemOut(BaseModel):
    """Target list item.

    Description:
        Represents a candidate cache that satisfies ≥1 task. `distance_km` is only present
        for "nearby" endpoints.

    Attributes:
        id (str): Target document id.
        user_challenge_id (str): Relevant UserChallenge.
        cache_id (str): Targeted cache.
        GC (str | None): GC code (if joined).
        name (str | None): Cache name (if joined).
        loc (LocOut | None): Coordinates (if joined).
        matched_task_ids (list[str]): Matched tasks.
        primary_task_id (str | None): Primary task.
        score (float): Sort score.
        reasons (list[str]): Textual reasons.
        pinned (bool): Pinned.
        distance_km (float | None): Distance (if nearby mode).
    """

    id: str  # target document id
    user_challenge_id: str
    cache_id: str

    # Cache summary (optional depending on the join performed by the service)
    GC: str | None = None
    name: str | None = None
    loc: LocOut | None = None

    matched_task_ids: list[str] = Field(default_factory=list)
    primary_task_id: str | None = None

    score: float
    reasons: list[str] = Field(default_factory=list)
    pinned: bool = False

    distance_km: float | None = None  # if ‘nearby’ search


class TargetListResponse(BaseModel):
    """Paginated target list response.

    Attributes:
        items (list[TargetListItemOut]): Results.
        nb_items (int): Total items found.
        page (int): Current page.
        page_size (int): Page size.
        nb_pages (int): Total pages.
    """

    items: list[TargetListItemOut]
    nb_items: int
    page: int
    page_size: int
    nb_pages: int


# ---- (Optional) "per-task" preview DTO ----


class MatchRef(BaseModel):
    """Covered (UC, Task) reference.

    Attributes:
        uc_id (str): Target UserChallenge.
        task_id (str): Covered task.
    """

    uc_id: str
    task_id: str


class TargetOut(BaseModel):
    """Enriched target (preview).

    Description:
        Optional detailed view when services perform joins/aggregations.

    Attributes:
        cache_id (str): Cache id.
        name (str): Cache name.
        loc (LocOut): Coordinates.
        type_id (str | None): Type.
        difficulty (float | None): D.
        terrain (float | None): T.
        matched (list[MatchRef]): Coverages.
        score (float): Score.
        reasons (list[str]): Reasons.
        distance_km (float | None): Distance (nearby).
        already_found (bool): Already found.
        pinned (bool): Pinned.
    """

    cache_id: str
    name: str
    loc: LocOut
    type_id: str | None = None
    difficulty: float | None = None
    terrain: float | None = None
    matched: list[MatchRef] = Field(default_factory=list)
    score: float
    reasons: list[str] = Field(default_factory=list)
    distance_km: float | None = None
    already_found: bool = False
    pinned: bool = False


class PerTaskBucket(BaseModel):
    """Candidate bucket per task.

    Attributes:
        uc_id (str): UserChallenge.
        task_id (str): Task.
        needed (int): Remaining to cover.
        candidates (list[TargetOut]): Proposed selection.
    """

    uc_id: str
    task_id: str
    needed: int
    candidates: list[TargetOut]


class TargetsPreviewPerTaskResponse(BaseModel):
    """Per-task preview response.

    Attributes:
        mode (Literal['per_task']): Mode indicator.
        buckets (list[PerTaskBucket]): Buckets per task.
        meta (dict): Free-form metadata.
    """

    mode: Literal["per_task"] = "per_task"
    buckets: list[PerTaskBucket]
    meta: dict[str, Any] = Field(default_factory=dict)


# ---- (Optional) "global" preview DTO ----


class CoverageGap(BaseModel):
    """Coverage gap.

    Attributes:
        uc_id (str): UserChallenge.
        task_id (str): Task.
        remaining (int): Remaining to cover.
    """

    uc_id: str
    task_id: str
    remaining: int


class TargetsPreviewGlobalResponse(BaseModel):
    """Global preview response.

    Attributes:
        mode (Literal['global']): Mode indicator.
        selection (list[TargetOut]): Global selection.
        covered_pairs (int): Covered (UC, Task) pairs.
        remaining (list[CoverageGap]): Remaining gaps.
        meta (dict): Free-form metadata.
    """

    mode: Literal["global"] = "global"
    selection: list[TargetOut]
    covered_pairs: int
    remaining: list[CoverageGap]
    meta: dict[str, Any] = Field(default_factory=dict)
