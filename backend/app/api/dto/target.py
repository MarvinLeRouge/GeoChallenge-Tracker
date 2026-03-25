# backend/app/models/target_dto.py
# Output schemas for target endpoints (lists, per-task, global).

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ---- Common types ----


class LocOut(BaseModel):
    """Decimal coordinates (lat/lng).

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
        Represents a candidate cache that satisfies ≥1 task.
        Accepts raw MongoDB documents: ObjectIds are coerced to strings and
        GeoJSON ``loc`` is converted to a ``{lat, lng}`` pair.

    Attributes:
        id (str): Target document id (from ``_id``).
        user_challenge_id (str): Relevant UserChallenge.
        cache_id (str): Targeted cache.
        cache_GC (str | None): GC code.
        cache_title (str | None): Cache name.
        cache_difficulty (float | None): Difficulty rating.
        cache_terrain (float | None): Terrain rating.
        loc (LocOut | None): Coordinates.
        primary_task_id (str | None): Primary matched task.
        matched_tasks_count (int): Number of tasks covered.
        score (float): Composite sort score.
        score_details (dict | None): Score breakdown.
        distance_m (float | None): Distance in metres (nearby mode only).
    """

    id: str
    user_challenge_id: str
    cache_id: str

    cache_GC: str | None = None
    cache_title: str | None = None
    cache_difficulty: float | None = None
    cache_terrain: float | None = None
    cache_type_code: str | None = None
    loc: LocOut | None = None

    primary_task_id: str | None = None
    matched_tasks_count: int = 0

    score: float
    score_details: dict[str, Any] | None = None

    distance_m: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_mongo_doc(cls, data: Any) -> Any:
        """Coerce ObjectIds → str and GeoJSON → LocOut before field validation."""
        if not isinstance(data, dict):
            return data

        # _id → id
        if "_id" in data:
            data["id"] = str(data["_id"])

        # ObjectId fields → str
        for field in ("cache_id", "user_challenge_id", "user_id", "primary_task_id"):
            if data.get(field) is not None:
                data[field] = str(data[field])

        # GeoJSON Point → {lat, lng}
        loc = data.get("loc")
        if isinstance(loc, dict) and loc.get("type") == "Point":
            coords = loc.get("coordinates", [])
            if len(coords) >= 2:
                data["loc"] = {"lng": coords[0], "lat": coords[1]}
            else:
                data["loc"] = None

        return data


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
