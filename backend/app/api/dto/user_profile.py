# backend/app/models/user_profile_dto.py
# Entrées/sorties pour la localisation utilisateur (texte ou coordonnées).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.bson_utils import PyObjectId
from app.core.utils import utcnow
from app.services.location_parser import format_coordinates_deg_min_mil


class UserLocationIn(BaseModel):
    """Entrée de localisation.

    Description:
        Deux formats acceptés :
        - coordonnées numériques (`lat`, `lon`)
        - chaîne `position` (DD/DM/DMS) à parser côté service.

    Attributes:
        lat (float | None): Latitude (-90..90).
        lon (float | None): Longitude (-180..180).
        position (str | None): Représentation texte des coordonnées.
    """

    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    position: str | None = None


class UserLocationOut(BaseModel):
    """Sortie de localisation utilisateur."""

    id: PyObjectId
    lat: float
    lon: float
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())

    @computed_field
    def coords(self) -> str:
        """Représentation en degrés/minutes (calculé automatiquement)."""
        return format_coordinates_deg_min_mil(self.lat, self.lon)

    model_config = ConfigDict(from_attributes=True)


class VerifyEmailBody(BaseModel):
    """Request body for email verification."""

    code: str
