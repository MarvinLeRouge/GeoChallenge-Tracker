# backend/app/services/user_challenge_tasks/task_expression_compiler.py
# Compilation des expressions AST vers filtres MongoDB - PRESERVATION EXACTE DE LA LOGIQUE

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain.models.challenge_ast import (
    RuleCountryIs,
    TaskAnd,
    TaskExpression,
    TaskNot,
    TaskOr,
)


class TaskExpressionCompiler:
    """Compilateur d'expressions AST vers filtres MongoDB.

    Description:
        Préservation EXACTE de la logique existante de compile_expression_to_cache_match.
        Aucune modification comportementale - juste réorganisation du code.
    """

    @staticmethod
    def compile_expression_to_cache_match(expr: TaskExpression) -> dict[str, Any]:
        """Compiler une expression AST vers un filtre Mongo `caches`.

        Description:
            FONCTION IDENTIQUE À L'ORIGINALE - Gère AND/OR/NOT pour les feuilles supportées ;
            ignore les feuilles d'agrégat (traitées ailleurs).

        Args:
            expr: Expression Pydantic déjà validée.

        Returns:
            dict: Filtre Mongo (peut contenir `$and/$or/$nor`).
        """

        def _leaf_to_match(leaf: Any) -> dict[str, Any]:
            k = getattr(leaf, "kind", None)

            if k == "type_in":
                # canonique: node.type_ids (liste d'OIDs)
                ids = [oid for oid in (getattr(leaf, "type_ids", None) or [])]
                return {"type_id": {"$in": ids}} if ids else {}

            if k == "size_in":
                ids = [oid for oid in (getattr(leaf, "size_ids", None) or [])]
                return {"size_id": {"$in": ids}} if ids else {}

            if k == "placed_year":
                y = int(leaf.year)
                return {"placed_year": y}

            if k == "placed_before":
                d = leaf.date
                return {"placed_at": {"$lt": d}}

            if k == "placed_after":
                d = leaf.date
                return {"placed_at": {"$gt": d}}

            if k == "difficulty_between":
                return {"difficulty": {"$gte": leaf.min, "$lte": leaf.max}}

            if k == "terrain_between":
                return {"terrain": {"$gte": leaf.min, "$lte": leaf.max}}

            if k == "country_is":
                return {"country_id": leaf.country_id}

            if k == "state_in":
                ids = [oid for oid in (getattr(leaf, "state_ids", None) or [])]
                return {"state_id": {"$in": ids}} if ids else {}

            if k == "attributes":
                # Liste d'attributs ET-és (tous doivent matcher)
                clauses: list[dict[str, Any]] = []
                for a in leaf.attributes:
                    # on privilégie cache_attribute_doc_id si présent, sinon id numérique
                    attr_doc_id = getattr(a, "cache_attribute_doc_id", None) or getattr(
                        a, "attribute_doc_id", None
                    )
                    num_id = getattr(a, "cache_attribute_id", None)
                    is_pos = bool(getattr(a, "is_positive", True))
                    sub: dict[str, Any] = {"attributes": {"$elemMatch": {"is_positive": is_pos}}}
                    if attr_doc_id:
                        sub["attributes"]["$elemMatch"]["attribute_doc_id"] = attr_doc_id
                    elif num_id is not None:
                        sub["attributes"]["$elemMatch"]["cache_attribute_id"] = int(num_id)
                    # sinon: si seulement "code" => interdit ici (doit avoir été normalisé avant)
                    clauses.append(sub)
                return {"$and": clauses} if clauses else {}

            # Agrégats: ne participent pas au filtre "cache" (calculés côté progress/metrics)
            if k in {
                "aggregate_sum_difficulty_at_least",
                "aggregate_sum_terrain_at_least",
                "aggregate_sum_diff_plus_terr_at_least",
                "aggregate_sum_altitude_at_least",
            }:
                return {}

            # Par défaut: rien
            return {}

        def _node(expr_node: Any) -> dict[str, Any]:
            if isinstance(expr_node, TaskAnd):
                parts = [_node(n) for n in expr_node.nodes]
                parts = [p for p in parts if p]  # strip empties
                return {"$and": parts} if parts else {}

            if isinstance(expr_node, TaskOr):
                parts = [_node(n) for n in expr_node.nodes]
                parts = [p for p in parts if p]
                return {"$or": parts} if parts else {}

            if isinstance(expr_node, TaskNot):
                inner = _node(expr_node.node)
                return {"$nor": [inner]} if inner else {}

            # Feuille
            return _leaf_to_match(expr_node)

        return _node(expr)

    @staticmethod
    def has_country_is_in_and(nodes: Iterable[Any]) -> bool:
        """Tester la présence d'un nœud `country_is` dans un AND.

        FONCTION IDENTIQUE À L'ORIGINALE _has_country_is.

        Args:
            nodes: Nœuds frères.

        Returns:
            bool: True si `country_is` trouvé.
        """
        for n in nodes:
            if isinstance(n, RuleCountryIs):
                return True
            # Si sous-AND imbriqué, on check récursivement
            if isinstance(n, TaskAnd) and TaskExpressionCompiler.has_country_is_in_and(n.nodes):
                return True
        return False

    @staticmethod
    def walk_expression_tree(expr: TaskExpression):
        """Itérer (kind, node, parent_kind) à des fins de validation structurelle.

        FONCTION IDENTIQUE À L'ORIGINALE _walk_expr.

        Args:
            expr: Expression à parcourir.

        Returns:
            Iterable[tuple[str, Any, str|None]]: Triplets (kind, node, parent).
        """
        if isinstance(expr, (TaskAnd, TaskOr)):
            parent = expr.kind
            for child in expr.nodes:
                for k, n, pk in TaskExpressionCompiler.walk_expression_tree(child):
                    yield (k, n, pk if pk is not None else parent)
            return
        if isinstance(expr, TaskNot):
            for k, n, _pk in TaskExpressionCompiler.walk_expression_tree(expr.node):
                yield (k, n, "not")
            return
        return [(expr.kind, expr, None)]

    @staticmethod
    def is_aggregate_kind(kind: str) -> bool:
        """Indiquer si `kind` correspond à une feuille d'agrégat.

        FONCTION IDENTIQUE À L'ORIGINALE _is_aggregate_kind.

        Args:
            kind: Nom de la règle.

        Returns:
            bool: True si agrégat.
        """
        return kind in (
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
        )
