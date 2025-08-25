# app/models/target.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict

from app.core.utils import utcnow
from app.core.bson_utils import PyObjectId, MongoBaseModel


# Schéma Mongo "targets"
# - 1 document par (user_challenge_id, cache_id)
# - dénormalisation minimale de la position (GeoJSON Point) pour $geoNear

class TargetCreate(BaseModel):
    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)

    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: Optional[Dict[str, Any]] = None

    # utile en debug, jamais exposé côté API publique
    diagnostics: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class TargetUpdate(BaseModel):
    satisfies_task_ids: Optional[List[PyObjectId]] = None
    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: Optional[bool] = None
    loc: Optional[Dict[str, Any]] = None
    diagnostics: Optional[Dict[str, Any]] = None
    updated_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class Target(MongoBaseModel):
    user_id: PyObjectId
    user_challenge_id: PyObjectId
    cache_id: PyObjectId

    primary_task_id: PyObjectId
    satisfies_task_ids: List[PyObjectId] = Field(default_factory=list)

    score: Optional[float] = None
    reasons: Optional[List[str]] = None
    pinned: bool = False

    # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
    loc: Optional[Dict[str, Any]] = None

    diagnostics: Optional[Dict[str, Any]] = None

    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: Optional[dt.datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )
