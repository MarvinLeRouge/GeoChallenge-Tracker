from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import datetime as dt
from app.core.bson_utils import *

class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None

    challenge_id: PyObjectId               # 🔗 lien obligatoire vers challenge

    # Type de filtre principal (ex: "attribute", "type", "country", etc.)
    filter_type: Literal["type", "attribute", "country", "county", "year", "month", "size", "other"]

    # Critères de filtrage (objectIds, années, etc.)
    criteria: List[str] | List[int] | List[PyObjectId]

    # Type d’opération
    operator: Literal["AND", "OR"] = "AND"

    # Groupement (optionnel) pour des cas avancés (ex: par pays, par mois)
    group_by: Optional[str] = None                   # ex: "country", "month", etc.
    target_unique: Optional[int] = None              # nombre de groupes différents requis
    target_per_group: Optional[int] = None           # nombre de caches dans chaque groupe

    required_count: Optional[int] = None             # ex: 500 caches

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    filter_type: Optional[str]
    criteria: Optional[List[str]]
    operator: Optional[str]
    group_by: Optional[str]
    target_unique: Optional[int]
    target_per_group: Optional[int]
    required_count: Optional[int]

class Task(TaskBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
