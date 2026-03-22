# backend/app/models/challenge.py
# Representation of a challenge and its metadata (source cache, description, analytics).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class ChallengeMeta(BaseModel):
    """Challenge meta-statistics.

    Description:
        Optional analytics data intended for stats screens.

    Attributes:
        avg_days_to_complete (float | None): Average days to complete.
        avg_caches_involved (float | None): Average number of caches involved.
        completions (int | None): Completion count.
        acceptance_rate (float | None): Acceptance rate.
    """

    avg_days_to_complete: float | None = None
    avg_caches_involved: float | None = None
    completions: int | None = None
    acceptance_rate: float | None = None


class ChallengeBase(BaseModel):
    """Base challenge fields.

    Description:
        References the "parent" cache and carries the name, description and metadata.

    Attributes:
        cache_id (PyObjectId): Ref to `caches._id`.
        name (str): Challenge name.
        description (str | None): Text description.
        meta (ChallengeMeta | None): Optional meta-statistics.
    """

    cache_id: PyObjectId  # ref -> caches._id ("parent" cache)
    name: str
    description: str | None = None
    meta: ChallengeMeta | None = None


class ChallengeCreate(ChallengeBase):
    """Challenge creation payload.

    Description:
        Identical to `ChallengeBase`; used as input for the admin API.
    """

    pass


class ChallengeUpdate(BaseModel):
    """Challenge update payload.

    Description:
        Partial field update.

    Attributes:
        cache_id (PyObjectId | None): New "parent" cache.
        name (str | None): New name.
        description (str | None): New description.
        meta (ChallengeMeta | None): New meta-statistics.
    """

    cache_id: PyObjectId | None = None
    name: str | None = None
    description: str | None = None
    meta: ChallengeMeta | None = None


class Challenge(MongoBaseModel, ChallengeBase):
    """Challenge Mongo document.

    Description:
        Extends `ChallengeBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
