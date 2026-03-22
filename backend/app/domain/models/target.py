# backend/app/models/target.py
# Represents a candidate cache (target) for a UserChallenge, with scoring, geo data and diagnostics.

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import utcnow

# ---------- Diagnostics structurés ----------


class TargetDiagnosticsSubscores(BaseModel):
    """Diagnostic sub-scores (0–1).

    Attributes:
        tasks (float): Share of incomplete tasks covered.
        urgency (float): Urgency (max ratio remaining/min_count).
        geo (float): Distance factor (1 if no geo constraint).
    """

    tasks: float = Field(ge=0.0, le=1.0)  # share of non-done tasks covered by this cache
    urgency: float = Field(ge=0.0, le=1.0)  # max ratio (remaining/min_count) among covered tasks
    geo: float = Field(ge=0.0, le=1.0)  # distance factor (1/(1+d/D0)) or 1 if no geo constraint


class TargetDiagnostics(BaseModel):
    """Full diagnostic block.

    Description:
        Details the matched tasks and sub-scores used for sorting/scoring.

    Attributes:
        matched (list[dict]): Match details (internal debug).
        subscores (TargetDiagnosticsSubscores): Target sub-scores.
        evaluated_at (datetime): UTC computation timestamp.
    """

    matched: list[dict[str, Any]] = Field(default_factory=list)
    subscores: TargetDiagnosticsSubscores
    evaluated_at: dt.datetime = Field(default_factory=utcnow)

    model_config = ConfigDict(json_encoders={PyObjectId: str})


# "targets" Mongo schema
# - 1 document per (user_challenge_id, cache_id)
# - minimal position denormalization (GeoJSON Point) for $geoNear


class TargetCreate(BaseModel):
    """Target upsert payload.

    Attributes:
        user_id (PyObjectId): User reference.
        user_challenge_id (PyObjectId): UC reference.
        cache_id (PyObjectId): Candidate cache reference.
        primary_task_id (PyObjectId): Primarily matched task.
        satisfies_task_ids (list[PyObjectId]): Other matched tasks.
        score (float | None): Sort score.
        reasons (list[str] | None): Textual reasons.
        pinned (bool): Pinned by the user.
        loc (dict | None): GeoJSON Point `[lon, lat]`.
        diagnostics (TargetDiagnostics | None): Internal diagnostic.
    """

    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: list[PyObjectId] = Field(default_factory=list)

    score: float | None = None
    reasons: list[str] | None = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: dict[str, Any] | None = None

    # useful for debug, never exposed via the public API
    diagnostics: TargetDiagnostics | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class TargetUpdate(BaseModel):
    """Target update payload.

    Attributes:
        satisfies_task_ids (list[PyObjectId] | None): Coverage adjustments.
        score (float | None): New score.
        reasons (list[str] | None): New reasons.
        pinned (bool | None): Pinned flag.
        loc (dict | None): GeoJSON Point.
        diagnostics (TargetDiagnostics | None): Diagnostic.
        updated_at (datetime | None): Update timestamp.
    """

    satisfies_task_ids: list[PyObjectId] | None = None
    score: float | None = None
    reasons: list[str] | None = None
    pinned: bool | None = None
    loc: dict[str, Any] | None = None
    diagnostics: TargetDiagnostics | None = None
    updated_at: dt.datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class Target(MongoBaseModel):
    """Target Mongo document.

    Description:
        1 document per (user_challenge_id, cache_id) pair. Denormalizes position for geo queries.

    Attributes:
        user_id (PyObjectId): User reference.
        user_challenge_id (PyObjectId): UC reference.
        cache_id (PyObjectId): Cache reference.
        primary_task_id (PyObjectId): Primary task.
        satisfies_task_ids (list[PyObjectId]): Covered tasks.
        score (float | None): Score.
        reasons (list[str] | None): Reasons.
        pinned (bool): Pinned.
        loc (dict | None): GeoJSON Point.
        diagnostics (TargetDiagnostics | None): Diagnostic.
        created_at (datetime): Creation time (UTC).
        updated_at (datetime | None): Last update (UTC).
    """

    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: list[PyObjectId] = Field(default_factory=list)

    score: float | None = None
    reasons: list[str] | None = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: dict[str, Any] | None = None

    diagnostics: TargetDiagnostics | None = None

    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )
