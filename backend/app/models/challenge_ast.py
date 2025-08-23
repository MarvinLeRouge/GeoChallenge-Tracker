# backend/app/models/challenge_ast.py

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, RootModel
from app.core.bson_utils import PyObjectId

class ASTBase(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
        populate_by_name=True,
    )

# ---- Cache-level leaves ----
## --- Selectors ---
class TypeSelector(ASTBase):
    cache_type_doc_id: Optional[PyObjectId] = None
    cache_type_id: Optional[int] = None
    cache_type_code: Optional[str] = Field(default=None, description="Cache type code, e.g. 'whereigo'")

class SizeSelector(ASTBase):
    cache_size_doc_id: Optional[PyObjectId] = None
    cache_size_id: Optional[int] = None
    code: Optional[str] = Field(default=None, description="Cache size code")

class StateSelector(ASTBase):
    state_id: Optional[int] = None
    name: Optional[str] = Field(default=None, description="Cache state")

class CountrySelector(ASTBase):
    country_id: Optional[int] = None
    name: Optional[str] = Field(default=None, description="Cache country")

class AttributeSelector(ASTBase):
    cache_attribute_doc_id: Optional[PyObjectId] = None
    cache_attribute_id: Optional[int] = None
    code: Optional[str] = Field(default=None, description="Cache attribute code, e.g. 'picnic'")
    is_positive: bool = True


## --- Rules ---
class RuleTypeIn(ASTBase):
    kind: Literal["type_in"] = "type_in"
    types: List[TypeSelector]

class RuleSizeIn(ASTBase):
    kind: Literal["size_in"] = "size_in"
    sizes: List[SizeSelector]

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
    country: CountrySelector

class RuleDifficultyBetween(ASTBase):
    kind: Literal["difficulty_between"] = "difficulty_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)

class RuleTerrainBetween(ASTBase):
    kind: Literal["terrain_between"] = "terrain_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)

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

# Les kinds logiques et les kinds "feuilles" (règles) connus
_LOGICAL_KINDS = {"and", "or", "not"}
_RULE_KINDS = {
    "attributes",
    "type_in",
    "size_in",
    "placed_year",
    "placed_before",
    "placed_after",
    "state_in",
    "country_is",
    "difficulty_between",
    "terrain_between",
    "aggregate_sum_difficulty_at_least",
    "aggregate_sum_terrain_at_least",
    "aggregate_sum_diff_plus_terr_at_least",
    "aggregate_sum_altitude_at_least",
}

def preprocess_expression_default_and(expr: Any) -> Any:
    """
    Transforme des écritures "courtes" en une expression canonique
    où 'kind'='and' est explicite et les règles sont dans 'nodes'.

    Règles :
    - Si expr est un dict sans 'kind', on considère que c'est un bloc 'and'.
      - Si le dict ressemble déjà à un nœud logique (a 'nodes'), on met kind='and'.
      - Si le dict ressemble à UNE règle (kind de règle OU clés de règle directes),
        on l'enveloppe dans {'kind':'and','nodes':[<règle>]}.
    - Si expr.kind ∈ RULE_KINDS (ex: 'type_in') au sommet, on enveloppe pareil.
    - Sinon on renvoie tel quel.

    Appelé AVANT la validation Pydantic sur l'AST.
    """
    # Cas non-dict (list, str, etc.) → inchangé
    if not isinstance(expr, dict):
        return expr

    # Si pas de 'kind' → c'est un AND implicite
    if "kind" not in expr:
        # Si déjà une liste de 'nodes', on force 'and'
        if "nodes" in expr and isinstance(expr["nodes"], list):
            return {"kind": "and", "nodes": expr["nodes"]}

        # Détection d'une "règle courte" (attributs/typage directs)
        looks_like_rule = any(k in expr for k in (
            "attributes", "type_ids", "codes", "size_ids",
            "year", "date", "state_ids", "country_id",
            "min", "max", "min_total"
        ))
        if looks_like_rule:
            return {"kind": "and", "nodes": [expr]}

        # Sinon, on met quand même un AND vide (laisser la validation gérer)
        return {"kind": "and", "nodes": expr.get("nodes", [])}

    # Si 'kind' est une règle au sommet → envelopper dans un AND
    k = expr.get("kind")
    if isinstance(k, str) and k in _RULE_KINDS:
        return {"kind": "and", "nodes": [expr]}

    # Si 'kind' est logique mais sans nodes et qu'on voit des champs de règle,
    # on transforme en nodes=[ ce dict moins 'kind' ] (rare, mais utile)
    if isinstance(k, str) and k in _LOGICAL_KINDS and not expr.get("nodes"):
        looks_like_rule = any(field in expr for field in (
            "attributes", "type_ids", "codes", "size_ids",
            "year", "date", "state_ids", "country_id",
            "min", "max", "min_total"
        ))
        if looks_like_rule:
            rule_like = {kk: vv for kk, vv in expr.items() if kk != "kind"}
            return {"kind": k, "nodes": [rule_like]}

    # Déjà canonique
    return expr
