# backend/app/models/cache.py
# Modèle principal d’une géocache (métadonnées, typage, localisation, attributs, stats).

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class CacheAttributeRef(BaseModel):
    """Référence d’attribut de cache.

    Description:
        Lien vers un document `cache_attributes` avec indication du sens (positif/négatif).

    Attributes:
        attribute_doc_id (PyObjectId): Référence à `cache_attributes._id`.
        is_positive (bool): True si l’attribut est affirmatif, False s’il est négatif.
    """

    attribute_doc_id: PyObjectId  # référence à cache_attributes._id
    is_positive: bool  # attribut positif (True) ou négatif (False)

    # Sous-modèle: ajouter model_config pour gérer PyObjectId partout (nested)
    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={PyObjectId: str})


class CacheBase(BaseModel):
    """Champs de base d’une géocache.

    Description:
        Structure commune pour la création/lecture des caches : identifiants GC, typage,
        localisation (lat/lon + GeoJSON), attributs, difficultés/terrain, dates et stats.

    Attributes:
        GC (str): Code unique de la cache (ex. "GC123AB").
        title (str): Titre public.
        description_html (str | None): Description HTML.
        url (str | None): URL source (ex. listing).
        type_id (PyObjectId | None): Réf. `CacheType`.
        size_id (PyObjectId | None): Réf. `CacheSize`.
        country_id (PyObjectId | None): Réf. `Country`.
        state_id (PyObjectId | None): Réf. État/région.
        lat (float | None): Latitude décimale.
        lon (float | None): Longitude décimale.
        loc (dict[str, Any] | None): Point GeoJSON `[lon, lat]` pour 2dsphere.
        elevation (int | None): Altitude en mètres.
        location_more (dict[str, Any] | None): Détails libres (ville, département…).
        difficulty (float | None): Note 1.0–5.0.
        terrain (float | None): Note 1.0–5.0.
        attributes (list[CacheAttributeRef]): Attributs (positifs/négatifs).
        placed_at (datetime | None): Date/heure de mise en place.
        owner (str | None): Propriétaire (texte).
        favorites (int | None): Compteur de favoris.
        status (Literal['active','disabled','archived'] | None): Statut.
    """

    GC: str
    title: str
    description_html: str | None = None
    url: str | None = None

    # Typage / classement
    type_id: PyObjectId | None = None  # ref -> CacheType
    size_id: PyObjectId | None = None  # ref -> CacheSize

    # Localisation
    country_id: PyObjectId | None = None  # ref -> Country
    state_id: PyObjectId | None = None  # ref -> State
    lat: float | None = None
    lon: float | None = None
    # GeoJSON pour index 2dsphere (coordonnées [lon, lat])
    loc: dict[str, Any] | None = None
    elevation: int | None = None  # en mètres (optionnel)
    location_more: dict[str, Any] | None = None  # infos libres (ville, département...)

    # Caractéristiques
    difficulty: float | None = None  # 1.0 .. 5.0
    terrain: float | None = None  # 1.0 .. 5.0
    attributes: list[CacheAttributeRef] = Field(default_factory=list)

    # Dates & stats
    placed_at: dt.datetime | None = None
    owner: str | None = None
    favorites: int | None = None
    status: Literal["active", "disabled", "archived"] | None = None


class CacheCreate(CacheBase):
    """Payload de création d’une géocache.

    Description:
        Identique à `CacheBase` ; sert d’entrée pour l’API de création/import.
    """

    pass


class CacheUpdate(BaseModel):
    """Payload de mise à jour partielle d’une géocache.

    Description:
        Champs modifiables usuels (titre, description, élévation, état, attributs, statut).

    Attributes:
        title (str | None): Nouveau titre.
        description_html (str | None): Nouvelle description.
        url (str | None): Nouvelle URL.
        elevation (int | None): Nouvelle altitude.
        state_id (PyObjectId | None): État/région.
        location_more (dict[str, Any] | None): Détails de localisation libres.
        attributes (list[CacheAttributeRef] | None): Nouvelle liste d’attributs.
        status (Literal['active','disabled','archived'] | None): Nouveau statut.
    """

    title: str | None = None
    description_html: str | None = None
    url: str | None = None
    elevation: int | None = None
    state_id: PyObjectId | None = None
    location_more: dict[str, Any] | None = None
    attributes: list[CacheAttributeRef] | None = None
    status: Literal["active", "disabled", "archived"] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={PyObjectId: str})


class Cache(MongoBaseModel, CacheBase):
    """Document Mongo d’une géocache (avec horodatage).

    Description:
        Étend `CacheBase` avec les champs de traçabilité (_id, created_at, updated_at).
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
