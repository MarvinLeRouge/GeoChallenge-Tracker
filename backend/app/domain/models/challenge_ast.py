# backend/app/models/challenge_ast.py
# AST describing task selectors/rules and the (and/or/not) logic for UserChallenge.

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import PyObjectId


class ASTBase(BaseModel):
    """Pydantic base for all AST nodes.

    Description:
        Enables `PyObjectId` encoders and `populate_by_name`, allows arbitrary types,
        to produce clean JSON/OpenAPI for Swagger.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
        populate_by_name=True,
    )


# ---- Cache-level leaves ----
## --- Selectors ---
class TypeSelector(ASTBase):
    """Cache type selector.

    Attributes:
        cache_type_doc_id (PyObjectId | None): Ref to `cache_types._id`.
        cache_type_id (int | None): Global numeric identifier.
        cache_type_code (str | None): Type code (e.g. "whereigo").
    """

    cache_type_doc_id: PyObjectId | None = None
    cache_type_id: int | None = None
    code: str | None = Field(default=None, description="Cache type code, e.g. 'whereigo'")


class SizeSelector(ASTBase):
    """Cache size selector.

    Attributes:
        cache_size_doc_id (PyObjectId | None): Ref to `cache_sizes._id`.
        cache_size_id (int | None): Global numeric identifier.
        code (str | None): Size code.
    """

    cache_size_doc_id: PyObjectId | None = None
    cache_size_id: int | None = None
    code: str | None = Field(default=None, description="Cache size code")


class StateSelector(ASTBase):
    """State/region selector.

    Attributes:
        state_id (int | None): Numeric identifier (reference data).
        name (str | None): State/region name.
    """

    state_id: int | None = None
    name: str | None = Field(default=None, description="Cache state")


class CountrySelector(ASTBase):
    """Country selector.

    Attributes:
        country_id (int | None): Numeric identifier (reference data).
        name (str | None): Country name.
    """

    country_id: int | None = None
    name: str | None = Field(default=None, description="Cache country")


class AttributeSelector(ASTBase):
    """Cache attribute selector.

    Attributes:
        cache_attribute_doc_id (PyObjectId | None): Ref to `cache_attributes._id`.
        cache_attribute_id (int | None): Global numeric identifier.
        code (str | None): Attribute code (e.g. "picnic").
        is_positive (bool): True if the attribute is affirmative.
    """

    cache_attribute_doc_id: PyObjectId | None = None
    cache_attribute_id: int | None = None
    code: str | None = Field(default=None, description="Cache attribute code, e.g. 'picnic'")
    is_positive: bool = True


## --- Rules ---
class RuleTypeIn(ASTBase):
    """Rule: type ∈ {…}."""

    kind: Literal["type_in"] = "type_in"
    types: list[TypeSelector]


class RuleSizeIn(ASTBase):
    """Rule: size ∈ {…}."""

    kind: Literal["size_in"] = "size_in"
    sizes: list[SizeSelector]


class RulePlacedYear(ASTBase):
    """Rule: cache placed in the given year (bounded at model level)."""

    kind: Literal["placed_year"] = "placed_year"
    year: int = Field(ge=1999, le=2100)


class RulePlacedBefore(ASTBase):
    """Rule: cache placed **before** the given date (inclusive/exclusive per evaluation logic)."""

    kind: Literal["placed_before"] = "placed_before"
    date: date


class RulePlacedAfter(ASTBase):
    """Rule: cache placed **after** the given date (inclusive/exclusive per evaluation logic)."""

    kind: Literal["placed_after"] = "placed_after"
    date: date


class RuleStateIn(ASTBase):
    """Rule: state ∈ {…} (list of ObjectIds)."""

    kind: Literal["state_in"] = "state_in"
    state_ids: list[PyObjectId]


class RuleCountryIs(ASTBase):
    """Rule: country == value (single selector)."""

    kind: Literal["country_is"] = "country_is"
    country: CountrySelector


class RuleDifficultyBetween(ASTBase):
    """Rule: difficulty ∈ [min, max] (1.0–5.0)."""

    kind: Literal["difficulty_between"] = "difficulty_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)


class RuleTerrainBetween(ASTBase):
    """Rule: terrain ∈ [min, max] (1.0–5.0)."""

    kind: Literal["terrain_between"] = "terrain_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)


class RuleAttributes(ASTBase):
    """Rule: set of attributes (±)."""

    kind: Literal["attributes"] = "attributes"
    attributes: list[AttributeSelector]


# ---- Aggregate leaves (apply to the set of eligible finds) ----
class RuleAggSumDifficultyAtLeast(ASTBase):
    """Aggregate rule: sum(difficulty) ≥ min_total (over the set of eligible finds)."""

    kind: Literal["aggregate_sum_difficulty_at_least"] = "aggregate_sum_difficulty_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumTerrainAtLeast(ASTBase):
    """Aggregate rule: sum(terrain) ≥ min_total (over the set of eligible finds)."""

    kind: Literal["aggregate_sum_terrain_at_least"] = "aggregate_sum_terrain_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumDiffPlusTerrAtLeast(ASTBase):
    """Aggregate rule: sum(difficulty+terrain) ≥ min_total."""

    kind: Literal["aggregate_sum_diff_plus_terr_at_least"] = "aggregate_sum_diff_plus_terr_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumAltitudeAtLeast(ASTBase):
    """Aggregate rule: sum(altitude) ≥ min_total."""

    kind: Literal["aggregate_sum_altitude_at_least"] = "aggregate_sum_altitude_at_least"
    min_total: int = Field(ge=1)


TaskLeaf = Union[
    RuleTypeIn,
    RuleSizeIn,
    RulePlacedYear,
    RulePlacedBefore,
    RulePlacedAfter,
    RuleStateIn,
    RuleCountryIs,
    RuleDifficultyBetween,
    RuleTerrainBetween,
    RuleAttributes,
    RuleAggSumDifficultyAtLeast,
    RuleAggSumTerrainAtLeast,
    RuleAggSumDiffPlusTerrAtLeast,
    RuleAggSumAltitudeAtLeast,
]


class TaskAnd(ASTBase):
    """Logical AND node.

    Attributes:
        nodes (list[TaskAnd | TaskOr | TaskNot | TaskLeaf]): Child nodes.
    """

    kind: Literal["and"] = "and"
    nodes: list[TaskAnd | TaskOr | TaskNot | TaskLeaf]


class TaskOr(ASTBase):
    """Logical OR node.

    Attributes:
        nodes (list[TaskAnd | TaskOr | TaskNot | TaskLeaf]): Child nodes.
    """

    kind: Literal["or"] = "or"
    nodes: list[TaskAnd | TaskOr | TaskNot | TaskLeaf]


class TaskNot(ASTBase):
    """Logical NOT node.

    Attributes:
        node (TaskAnd | TaskOr | TaskLeaf): Child node.
    """

    kind: Literal["not"] = "not"
    node: TaskAnd | TaskOr | TaskLeaf


TaskExpression = TaskAnd | TaskOr | TaskNot | TaskLeaf
TaskAnd.model_rebuild()
TaskOr.model_rebuild()
TaskNot.model_rebuild()


# ---- UC-level logic (composition by task ids, unchanged) ----
class UCAnd(ASTBase):
    """UC logic: AND of `task_ids`."""

    kind: Literal["and"] = "and"
    task_ids: list[PyObjectId]


class UCOr(ASTBase):
    """UC logic: OR of `task_ids`."""

    kind: Literal["or"] = "or"
    task_ids: list[PyObjectId]


class UCNot(ASTBase):
    """UC logic: NOT of a `task_id`."""

    kind: Literal["not"] = "not"
    task_id: PyObjectId


UCLogic = Union[UCAnd, UCOr, UCNot]

# Known logical kinds and "leaf" (rule) kinds
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
    """Normalizes a shorthand expression to an explicit `AND`.

    Description:
        Transforms abbreviated expressions (missing `kind`, with direct rules, etc.)
        into a canonical structure where `kind=’and’` and rules are in `nodes`.
        Called **before** Pydantic validation of the AST.

    Args:
        expr (Any): Raw expression (dict/objects/…).

    Returns:
        Any: Normalized expression (dict) ready for validation.
    """
    # Non-dict case (list, str, etc.) → unchanged
    if not isinstance(expr, dict):
        return expr

    # No ‘kind’ → treat as implicit AND
    if "kind" not in expr:
        # Already has a ‘nodes’ list → force ‘and’
        if "nodes" in expr and isinstance(expr["nodes"], list):
            return {"kind": "and", "nodes": expr["nodes"]}

        # Detect a "short rule" (direct attributes/type fields)
        looks_like_rule = any(
            k in expr
            for k in (
                "attributes",
                "type_ids",
                "codes",
                "size_ids",
                "year",
                "date",
                "state_ids",
                "country_id",
                "min",
                "max",
                "min_total",
            )
        )
        if looks_like_rule:
            return {"kind": "and", "nodes": [expr]}

        # Otherwise, still wrap in an empty AND (let validation handle it)
        return {"kind": "and", "nodes": expr.get("nodes", [])}

    # ‘kind’ is a rule at the top level → wrap in an AND
    k = expr.get("kind")
    if isinstance(k, str) and k in _RULE_KINDS:
        return {"kind": "and", "nodes": [expr]}

    # ‘kind’ is logical but has no nodes and rule fields are present →
    # transform into nodes=[ this dict minus ‘kind’ ] (rare but useful)
    if isinstance(k, str) and k in _LOGICAL_KINDS and not expr.get("nodes"):
        looks_like_rule = any(
            field in expr
            for field in (
                "attributes",
                "type_ids",
                "codes",
                "size_ids",
                "year",
                "date",
                "state_ids",
                "country_id",
                "min",
                "max",
                "min_total",
            )
        )
        if looks_like_rule:
            rule_like = {kk: vv for kk, vv in expr.items() if kk != "kind"}
            return {"kind": k, "nodes": [rule_like]}

    # Already canonical
    return expr
