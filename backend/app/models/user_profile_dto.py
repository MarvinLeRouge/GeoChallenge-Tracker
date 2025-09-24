# backend/app/models/user_profile_dto.py
# Entrées/sorties pour la localisation utilisateur (texte ou coordonnées).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.utils import utcnow


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
    """Sortie de localisation.

    Attributes:
        lat (float): Latitude.
        lon (float): Longitude.
        coords (str | None): Représentation DM (si calculée).
        updated_at (datetime): Dernière mise à jour (UTC).
    """

    lat: float
    lon: float
    coords: str | None = ""
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())
