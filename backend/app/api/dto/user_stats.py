# backend/app/models/user_stats_dto.py
# DTOs for user statistics

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId


class CacheTypeStats(BaseModel):
    """Statistics for a specific cache type.

    Attributes:
        type_id (PyObjectId): Cache type identifier.
        type_label (str): Cache type label.
        type_code (str): Cache type code.
        count (int): Number of caches found of this type.
    """

    type_id: PyObjectId
    type_label: str
    type_code: str
    count: int = Field(ge=0, description="Number of caches found of this type")


class UserStatsOut(BaseModel):
    """Summary statistics for a user.

    Attributes:
        user_id (PyObjectId): User identifier.
        username (str): Username.
        total_caches_found (int): Total number of caches found.
        total_challenges (int): Total number of challenges.
        active_challenges (int): Number of active challenges (accepted).
        completed_challenges (int): Number of completed challenges.
        first_cache_found_at (datetime | None): Date of the first found cache.
        last_cache_found_at (datetime | None): Date of the most recent found cache.
        created_at (datetime): Account creation date.
        last_activity_at (datetime | None): Last activity (cache found or challenge created).
        cache_types_stats (list[CacheTypeStats] | None): Statistics by cache type.
    """

    user_id: PyObjectId
    username: str
    total_caches_found: int = Field(ge=0, description="Total number of caches found")
    total_challenges: int = Field(ge=0, description="Total number of challenges")
    active_challenges: int = Field(ge=0, description="Active challenges (accepted)")
    completed_challenges: int = Field(ge=0, description="Completed challenges")
    first_cache_found_at: Optional[datetime] = Field(
        None, description="Date of the first found cache"
    )
    last_cache_found_at: Optional[datetime] = Field(
        None, description="Date of the most recent found cache"
    )
    created_at: datetime = Field(description="Account creation date")
    last_activity_at: Optional[datetime] = Field(None, description="Last activity")
    cache_types_stats: Optional[list[CacheTypeStats]] = Field(
        None, description="Statistics by cache type"
    )
