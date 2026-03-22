# backend/app/models/user_profile_dto.py
# Input/output schemas for user location (text or coordinates).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.bson_utils import PyObjectId
from app.core.utils import utcnow
from app.services.location_parser import format_coordinates_deg_min_mil


class UserLocationIn(BaseModel):
    """Location input.

    Description:
        Two accepted formats:
        - numeric coordinates (`lat`, `lon`)
        - `position` string (DD/DM/DMS) to be parsed by the service.

    Attributes:
        lat (float | None): Latitude (-90..90).
        lon (float | None): Longitude (-180..180).
        position (str | None): Text representation of coordinates.
    """

    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    position: str | None = None


class UserLocationOut(BaseModel):
    """User location output."""

    id: PyObjectId
    lat: float
    lon: float
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())

    @computed_field
    def coords(self) -> str:
        """Degrees/minutes representation (computed automatically)."""
        return format_coordinates_deg_min_mil(self.lat, self.lon)

    model_config = ConfigDict(from_attributes=True)


class VerifyEmailBody(BaseModel):
    """Request body for email verification."""

    code: str
