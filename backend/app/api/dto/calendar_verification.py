"""Models for calendar and matrix verification functionality."""

from typing import Optional

from pydantic import BaseModel


class CalendarResult(BaseModel):
    """Result of calendar verification for a user."""

    # 365 days validation
    total_days_365: int = 365
    completed_days_365: int
    completion_rate_365: float
    calendar_tours: int = 0

    # 366 days validation (leap year)
    total_days_366: int = 366
    completed_days_366: int
    completion_rate_366: float

    # Common data
    missing_days: list[str]  # ["01-15", "03-22", ...] - missing in both 365 and 366
    missing_days_by_month: dict[str, list[str]]  # {"01": ["01-15", "01-22"], "03": ["03-10"], ...}
    completed_days: list[dict]  # [{"day": "01-01", "count": 2}, ...]

    # Filters applied
    cache_type_filter: Optional[str] = None
    cache_size_filter: Optional[str] = None


class CalendarFilters(BaseModel):
    """Filters for calendar verification."""

    cache_type_name: Optional[str] = None
    cache_size_name: Optional[str] = None


class MatrixResult(BaseModel):
    """Result of matrix D/T verification for a user."""

    # Matrix completion
    total_combinations: int = 81  # 9x9 matrix (1.0-5.0 by 0.5)
    completed_combinations_count: int
    completion_rate: float
    matrix_tours: int = 0
    next_round_completed_count: int
    next_round_completion_rate: float

    # Detailed data
    missing_combinations: list[dict]  # [{"difficulty": 1.0, "terrain": 2.0}, ...]
    missing_combinations_by_difficulty: dict[
        str, list[dict]
    ]  # {"1.0": [{"terrain": 2.0}, ...], ...}
    completed_combinations_details: list[
        dict
    ]  # [{"difficulty": 1.0, "terrain": 2.0, "count": 3}, ...]

    # Filters applied
    cache_type_filter: Optional[str] = None
    cache_size_filter: Optional[str] = None


class MatrixFilters(BaseModel):
    """Filters for matrix verification."""

    cache_type_name: Optional[str] = None
    cache_size_name: Optional[str] = None
