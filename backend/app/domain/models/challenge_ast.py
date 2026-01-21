# backend/app/models/challenge_ast.py
# AST décrivant les sélecteurs/règles de tâches et la logique (and/or/not) côté UserChallenge.

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.core.bson_utils import PyObjectId


class ASTBase(BaseModel):
    """Base Pydantic pour tous les nœuds AST.

    Description:
        Active les encoders `PyObjectId` et `populate_by_name`, tolère les types arbitraires,
        afin d’obtenir un JSON/OpenAPI propre pour Swagger.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
        populate_by_name=True,
    )


# ---- Cache-level leaves ----
## --- Selectors ---
class TypeSelector(ASTBase):
    """Sélecteur par type de cache.

    Attributes:
        cache_type_doc_id (PyObjectId | None): Réf. `cache_types._id`.
        cache_type_id (int | None): Identifiant numérique global.
        cache_type_code (str | None): Code type (ex. "whereigo").
    """

    cache_type_doc_id: PyObjectId | None = None
    cache_type_id: int | None = None
    code: str | None = Field(default=None, description="Cache type code, e.g. 'whereigo'")


class SizeSelector(ASTBase):
    """Sélecteur par taille de cache.

    Attributes:
        cache_size_doc_id (PyObjectId | None): Réf. `cache_sizes._id`.
        cache_size_id (int | None): Identifiant numérique global.
        code (str | None): Code de taille.
    """

    cache_size_doc_id: PyObjectId | None = None
    cache_size_id: int | None = None
    code: str | None = Field(default=None, description="Cache size code")


class StateSelector(ASTBase):
    """Sélecteur par État/région.

    Attributes:
        state_id (int | None): Identifiant numérique (référentiel).
        name (str | None): Nom de l’État/région.
    """

    state_id: int | None = None
    name: str | None = Field(default=None, description="Cache state")


class CountrySelector(ASTBase):
    """Sélecteur par pays.

    Attributes:
        country_id (int | None): Identifiant numérique (référentiel).
        name (str | None): Nom du pays.
    """

    country_id: int | None = None
    name: str | None = Field(default=None, description="Cache country")


class AttributeSelector(ASTBase):
    """Sélecteur par attribut(s) de cache.

    Attributes:
        cache_attribute_doc_id (PyObjectId | None): Réf. `cache_attributes._id`.
        cache_attribute_id (int | None): Identifiant numérique global.
        code (str | None): Code attribut (ex. "picnic").
        is_positive (bool): True si l’attribut est affirmatif.
    """

    cache_attribute_doc_id: PyObjectId | None = None
    cache_attribute_id: int | None = None
    code: str | None = Field(default=None, description="Cache attribute code, e.g. 'picnic'")
    is_positive: bool = True


## --- Rules ---
class RuleTypeIn(ASTBase):
    """Règle: type ∈ {…}."""

    kind: Literal["type_in"] = "type_in"
    types: list[TypeSelector]


class RuleSizeIn(ASTBase):
    """Règle: taille ∈ {…}."""

    kind: Literal["size_in"] = "size_in"
    sizes: list[SizeSelector]


class RulePlacedYear(ASTBase):
    """Règle: cache placée l’année donnée (bornée côté modèle)."""

    kind: Literal["placed_year"] = "placed_year"
    year: int = Field(ge=1999, le=2100)


class RulePlacedBefore(ASTBase):
    """Règle: cache placée **avant** la date donnée (incluse/exclue selon logique d’évaluation)."""

    kind: Literal["placed_before"] = "placed_before"
    date: date


class RulePlacedAfter(ASTBase):
    """Règle: cache placée **après** la date donnée (incluse/exclue selon logique d’évaluation)."""

    kind: Literal["placed_after"] = "placed_after"
    date: date


class RuleStateIn(ASTBase):
    """Règle: État ∈ {…} (liste d’ObjectId)."""

    kind: Literal["state_in"] = "state_in"
    state_ids: list[PyObjectId]


class RuleCountryIs(ASTBase):
    """Règle: pays == valeur (sélecteur unique)."""

    kind: Literal["country_is"] = "country_is"
    country: CountrySelector


class RuleDifficultyBetween(ASTBase):
    """Règle: difficulté ∈ [min, max] (1.0–5.0)."""

    kind: Literal["difficulty_between"] = "difficulty_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)


class RuleTerrainBetween(ASTBase):
    """Règle: terrain ∈ [min, max] (1.0–5.0)."""

    kind: Literal["terrain_between"] = "terrain_between"
    min: float = Field(ge=1.0, le=5.0)
    max: float = Field(ge=1.0, le=5.0)


class RuleAttributes(ASTBase):
    """Règle: ensemble d’attributs (±)."""

    kind: Literal["attributes"] = "attributes"
    attributes: list[AttributeSelector]


# ---- Aggregate leaves (apply to the set of eligible finds) ----
class RuleAggSumDifficultyAtLeast(ASTBase):
    """Règle agrégée: somme(difficulté) ≥ min_total (sur l’ensemble de trouvailles éligibles)."""

    kind: Literal["aggregate_sum_difficulty_at_least"] = "aggregate_sum_difficulty_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumTerrainAtLeast(ASTBase):
    """Règle agrégée: somme(terrain) ≥ min_total (sur l’ensemble de trouvailles éligibles)."""

    kind: Literal["aggregate_sum_terrain_at_least"] = "aggregate_sum_terrain_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumDiffPlusTerrAtLeast(ASTBase):
    """Règle agrégée: somme(difficulté+terrain) ≥ min_total."""

    kind: Literal["aggregate_sum_diff_plus_terr_at_least"] = "aggregate_sum_diff_plus_terr_at_least"
    min_total: int = Field(ge=1)


class RuleAggSumAltitudeAtLeast(ASTBase):
    """Règle agrégée: somme(altitude) ≥ min_total."""

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
    """Nœud logique AND.

    Attributes:
        nodes (list[TaskAnd | TaskOr | TaskNot | TaskLeaf]): Sous-nœuds.
    """

    kind: Literal["and"] = "and"
    nodes: list[TaskAnd | TaskOr | TaskNot | TaskLeaf]


class TaskOr(ASTBase):
    """Nœud logique OR.

    Attributes:
        nodes (list[TaskAnd | TaskOr | TaskNot | TaskLeaf]): Sous-nœuds.
    """

    kind: Literal["or"] = "or"
    nodes: list[TaskAnd | TaskOr | TaskNot | TaskLeaf]


class TaskNot(ASTBase):
    """Nœud logique NOT.

    Attributes:
        node (TaskAnd | TaskOr | TaskLeaf): Sous-nœud.
    """

    kind: Literal["not"] = "not"
    node: TaskAnd | TaskOr | TaskLeaf


TaskExpression = TaskAnd | TaskOr | TaskNot | TaskLeaf
TaskAnd.model_rebuild()
TaskOr.model_rebuild()
TaskNot.model_rebuild()


# ---- UC-level logic (composition by task ids, unchanged) ----
class UCAnd(ASTBase):
    """Logique UC: AND des `task_ids`."""

    kind: Literal["and"] = "and"
    task_ids: list[PyObjectId]


class UCOr(ASTBase):
    """Logique UC: OR des `task_ids`."""

    kind: Literal["or"] = "or"
    task_ids: list[PyObjectId]


class UCNot(ASTBase):
    """Logique UC: NOT d’un `task_id`."""

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
    """Normalise une expression courte en `AND` explicite.

    Description:
        Transforme les écritures abrégées (sans `kind`, avec règles directes, etc.)
        en une structure canonique où `kind='and'` et les règles sont dans `nodes`.
        Appelée **avant** la validation Pydantic de l’AST.

    Args:
        expr (Any): Expression brute (dict/objets/…).

    Returns:
        Any: Expression normalisée (dict) prête pour la validation.
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

        # Sinon, on met quand même un AND vide (laisser la validation gérer)
        return {"kind": "and", "nodes": expr.get("nodes", [])}

    # Si 'kind' est une règle au sommet → envelopper dans un AND
    k = expr.get("kind")
    if isinstance(k, str) and k in _RULE_KINDS:
        return {"kind": "and", "nodes": [expr]}

    # Si 'kind' est logique mais sans nodes et qu'on voit des champs de règle,
    # on transforme en nodes=[ ce dict moins 'kind' ] (rare, mais utile)
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

    # Déjà canonique
    return expr
