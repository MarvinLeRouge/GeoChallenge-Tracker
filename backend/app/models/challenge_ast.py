# backend/app/models/challenge_ast.py

from __future__ import annotations
from typing import List, Literal, Optional, Union
from datetime import date
from pydantic import BaseModel, Field, ConfigDict
from app.core.bson_utils import PyObjectId

class ASTBase(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
        populate_by_name=True,
    )

# ---- Cache-level leaves ----
class RuleTypeIn(ASTBase):
    kind: Literal["type_in"] = "type_in"
    type_ids: List[PyObjectId]

class RuleSizeIn(ASTBase):
    kind: Literal["size_in"] = "size_in"
    size_ids: List[PyObjectId]

class RulePlacedYear(ASTBase):
    kind: Literal["placed_year"] = "placed_year"
    year: int = Field(ge=1999, le=2100)

class RulePlacedBefore(ASTBase):
    kind: Literal["placed_before"] = "placed_before"
    date: date

class RulePlacedAfter(ASTBase):
    kind: Literal["placed_after"] = "placed_after"
    date: date

class RuleStateIn(ASTBase):
    kind: Literal["state_in"] = "state_in"
    state_ids: List[PyObjectId]

class RuleCountryIs(ASTBase):
    kind: Literal["country_is"] = "country_is"
    country_id: PyObjectId

class RuleDifficultyBetween(ASTBase):
    kind: Literal["difficulty_between"] = "difficulty_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)

class RuleTerrainBetween(ASTBase):
    kind: Literal["terrain_between"] = "terrain_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)

class AttributeSelector(ASTBase):
    cache_attribute_id: int
    attribute_doc_id: Optional[PyObjectId] = None
    is_positive: bool = True

class RuleAttributes(ASTBase):
    kind: Literal["attributes"] = "attributes"
    attributes: List[AttributeSelector]

# ---- Aggregate leaves (apply to the set of eligible finds) ----
class RuleAggSumDifficultyAtLeast(ASTBase):
    kind: Literal["aggregate_sum_difficulty_at_least"] = "aggregate_sum_difficulty_at_least"
    min_total: int = Field(ge=1)

class RuleAggSumTerrainAtLeast(ASTBase):
    kind: Literal["aggregate_sum_terrain_at_least"] = "aggregate_sum_terrain_at_least"
    min_total: int = Field(ge=1)

class RuleAggSumDiffPlusTerrAtLeast(ASTBase):
    kind: Literal["aggregate_sum_diff_plus_terr_at_least"] = "aggregate_sum_diff_plus_terr_at_least"
    min_total: int = Field(ge=1)

class RuleAggSumAltitudeAtLeast(ASTBase):
    kind: Literal["aggregate_sum_altitude_at_least"] = "aggregate_sum_altitude_at_least"
    min_total: int = Field(ge=1)

TaskLeaf = Union[
    RuleTypeIn, RuleSizeIn, RulePlacedYear, RulePlacedBefore, RulePlacedAfter,
    RuleStateIn, RuleCountryIs, RuleDifficultyBetween, RuleTerrainBetween,
    RuleAttributes,
    RuleAggSumDifficultyAtLeast, RuleAggSumTerrainAtLeast, RuleAggSumDiffPlusTerrAtLeast, RuleAggSumAltitudeAtLeast,
]

class TaskAnd(ASTBase):
    kind: Literal["and"] = "and"
    nodes: List[Union["TaskAnd", "TaskOr", "TaskNot", TaskLeaf]]

class TaskOr(ASTBase):
    kind: Literal["or"] = "or"
    nodes: List[Union["TaskAnd", "TaskOr", "TaskNot", TaskLeaf]]

class TaskNot(ASTBase):
    kind: Literal["not"] = "not"
    node: Union["TaskAnd", "TaskOr", TaskLeaf]

TaskExpression = Union[TaskAnd, TaskOr, TaskNot, TaskLeaf]
TaskAnd.model_rebuild(); TaskOr.model_rebuild(); TaskNot.model_rebuild()

# ---- UC-level logic (composition by task ids, unchanged) ----
class UCAnd(ASTBase):
    kind: Literal["and"] = "and"
    task_ids: List[PyObjectId]

class UCOr(ASTBase):
    kind: Literal["or"] = "or"
    task_ids: List[PyObjectId]

class UCNot(ASTBase):
    kind: Literal["not"] = "not"
    task_id: PyObjectId

UCLogic = Union[UCAnd, UCOr, UCNot]
