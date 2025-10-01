# backend/app/models/user_profile_dto.py
# Entrées/sorties pour la localisation utilisateur (texte ou coordonnées).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, computed_field, ConfigDict

from app.core.utils import utcnow

from app.core.bson_utils import PyObjectId

from app.services.user_profile import coords_in_deg_min_mil



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
    @property
    def coords(self) -> str:
        """Représentation en degrés/minutes (calculé automatiquement)."""
        return coords_in_deg_min_mil(self.lat, self.lon)
    
    model_config = ConfigDict(from_attributes=True)

