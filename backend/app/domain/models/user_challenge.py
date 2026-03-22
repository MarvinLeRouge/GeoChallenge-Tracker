# backend/app/models/user_challenge.py
# State of a challenge for a user (declared/computed statuses, UC logic, notes, progress).

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now
from app.domain.models.challenge_ast import UCLogic
from app.shared.progress import ProgressSnapshot


class UserChallenge(MongoBaseModel):
    """UserChallenge Mongo document.

    Description:
        Links a user to a challenge, stores the user-declared status and the
        computed status (UC logic evaluation), along with the manual override and a current snapshot.

    Attributes:
        user_id (PyObjectId): User reference.
        challenge_id (PyObjectId): Challenge reference.
        status (Literal[‘pending’,’accepted’,’dismissed’,’completed’]): Declared status.
        computed_status (Literal[...] | None): Computed status.
        manual_override (bool): Active manual override.
        override_reason (str | None): Override justification.
        overridden_at (datetime | None): Override date.
        logic (UCLogic | None): Task aggregation logic.
        progress (ProgressSnapshot | None): Current global snapshot.
        notes (str | None): Free-form notes.
        created_at (datetime): Creation time (local).
        updated_at (datetime | None): Last update.
    """

    user_id: PyObjectId
    challenge_id: PyObjectId
    # USER declaration (may be "completed" even if algorithmically not satisfied)
    status: Literal["pending", "accepted", "dismissed", "completed"] = "pending"

    # COMPUTED status from evaluation (UCLogic over tasks)
    computed_status: Literal["pending", "accepted", "dismissed", "completed"] | None = None

    # Override audit trail
    manual_override: bool = False
    override_reason: str | None = None
    overridden_at: dt.datetime | None = None
    logic: UCLogic | None = None
    # Aggregated, current snapshot for the whole challenge (redundant with history in Progress collection)
    progress: ProgressSnapshot | None = None
    notes: str | None = None

    # Projection
    estimated_completion_at: dt.datetime | None = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
