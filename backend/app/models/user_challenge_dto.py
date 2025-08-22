
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.bson_utils import PyObjectId

class PatchUCIn(BaseModel):
    status: Optional[str] = Field(default=None, description="pending|accepted|dismissed|completed")
    notes: Optional[str] = None
    override_reason: Optional[str] = Field(default=None, description="Optionnel si status=completed (override manuel)")

class ChallengeMini(BaseModel):
    id: PyObjectId
    name: str

class ListItem(BaseModel):
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    progress: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    challenge: ChallengeMini

class ListResponse(BaseModel):
    items: List[ListItem]
    page: int
    limit: int
    total: int

class CacheDetail(BaseModel):
    id: PyObjectId
    GC: str

class ChallengeDetail(BaseModel):
    id: PyObjectId
    name: str
    description: Optional[str] = None

class DetailResponse(BaseModel):
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    progress: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    manual_override: Optional[bool] = None
    override_reason: Optional[str] = None
    overridden_at: Optional[datetime] = None
    notes: Optional[str] = None
    challenge: ChallengeDetail
    cache: CacheDetail


class PatchResponse(BaseModel):
    id: PyObjectId
    status: str
    computed_status: Optional[str] = None
    effective_status: str
    manual_override: Optional[bool] = None
    override_reason: Optional[str] = None
    overridden_at: Optional[datetime] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None
