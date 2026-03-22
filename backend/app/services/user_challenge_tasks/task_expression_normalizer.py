# backend/app/services/user_challenge_tasks/task_expression_normalizer.py
# AST expression normalization — exact preservation of the logic.

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from app.domain.models.challenge_ast import TaskExpression
from app.domain.models.challenge_ast import TaskExpression as TE
from app.services.referentials_cache import (
    resolve_attribute_code,
    resolve_country_name,
    resolve_size_code,
    resolve_size_name,
    resolve_state_name,
    resolve_type_code,
)


class TaskExpressionNormalizer:
    """AST expression normalizer.

    Description:
        Exact preservation of the existing _normalize_code_to_id and
        _legacy_fixup_expression logic.
        No behavioral changes — purely code reorganization.
    """

    @staticmethod
    def normalize_code_to_id(expr: TaskExpression, *, index_for_errors: int) -> TaskExpression:
        """Normalize codes/labels to ObjectIds in the AST.

        FUNCTION IDENTICAL TO THE ORIGINAL _normalize_code_to_id.

        Description:
            - Attributes: `code` → `cache_attribute_doc_id` (+ `cache_attribute_id`).
            - Type: `cache_type_code` → `cache_type_doc_id`.
            - Size: `code`/`name` → `cache_size_doc_id`.
            - Country/State: resolved by name/code with explicit errors.

        Args:
            expr: Validated expression.
            index_for_errors: Task index (for error messages).

        Returns:
            TaskExpression: Expression enriched with identifiers.
        """

        def _norm(node: Any) -> Any:
            if isinstance(node, dict):
                k = node.get("kind")

                # --- attributes: code -> cache_attribute_doc_id (+ cache_attribute_id if known)
                if k == "attributes" and isinstance(node.get("attributes"), list):
                    new_attrs = []
                    for a in node["attributes"]:
                        a = dict(a)
                        code = a.get("code")
                        # NOTE: the AST model expects 'cache_attribute_doc_id'
                        if code and not a.get("cache_attribute_doc_id"):
                            res = resolve_attribute_code(code)  # must return (oid, numeric_id)
                            if not res:
                                raise ValueError(
                                    f"index {index_for_errors}: attribute code not found '{code}'"
                                )
                            doc_id, num_id = res
                            a["cache_attribute_doc_id"] = doc_id
                            # do not overwrite if already present
                            a.setdefault("cache_attribute_id", num_id)
                        new_attrs.append(a)
                    node = {**node, "attributes": new_attrs}

                # --- type_in: cache_type_code -> cache_type_doc_id
                elif k == "type_in" and isinstance(node.get("types"), list):
                    new_types = []
                    for t in node["types"]:
                        t = dict(t)
                        if t.get("cache_type_code") and not t.get("cache_type_doc_id"):
                            found = resolve_type_code(
                                t["cache_type_code"]
                            )  # returns the OID of the type doc
                            if not found:
                                raise ValueError(
                                    f"index {index_for_errors}: type code not found '{t['cache_type_code']}'"
                                )
                            t["cache_type_doc_id"] = found
                        new_types.append(t)
                    node = {**node, "types": new_types}

                # --- size_in: code/name -> cache_size_doc_id
                elif k == "size_in" and isinstance(node.get("sizes"), list):
                    new_sizes = []
                    for s in node["sizes"]:
                        s = dict(s)
                        if not s.get("cache_size_doc_id"):
                            found = None
                            if s.get("code"):
                                found = resolve_size_code(s["code"])
                            elif s.get("name"):
                                found = resolve_size_name(s["name"])
                            if not found:
                                label = s.get("code") or s.get("name") or "<?>"
                                raise ValueError(
                                    f"index {index_for_errors}: size not found '{label}'"
                                )
                            s["cache_size_doc_id"] = found
                        new_sizes.append(s)
                    node = {**node, "sizes": new_sizes}

                # --- country_is: accept {"country": {"code" | "name"}} and keep readable fields
                elif k == "country_is":
                    c = dict(node.get("country") or {})
                    if not node.get("country_id"):
                        cid = None
                        if (not cid) and c.get("name"):
                            cid = resolve_country_name(c["name"])
                        if not cid:
                            label = c.get("code") or c.get("name") or "<?>"
                            raise ValueError(
                                f"country_is: country not found '{label}' (index {index_for_errors})"
                            )
                        node["country_id"] = cid
                    # keep the 'country' block as provided (for GET readability)
                    node["country"] = c or node.get("country") or {}

                # --- state_in: accept {"states":[{"name": ...}]} (and/or "state_names": [...])
                #               requires the country from the same AND
                #               (already validated by validate_task_expression)
                elif k == "state_in":
                    # collect ids from multiple accepted forms
                    state_ids = list(node.get("state_ids") or [])
                    # short compat form: state_names: ["X","Y"]
                    for nm in node.get("state_names") or []:
                        state_id, _ = resolve_state_name(
                            nm,
                            country_id=node.get("country_id")
                            or (node.get("country") or {}).get("country_id"),
                        )
                        if not state_id:
                            raise ValueError(
                                f"state_in: state not found '{nm}' (index {index_for_errors})"
                            )
                        state_ids.append(state_id)
                    # rich form: states: [{"name": ...}]
                    for s in node.get("states") or []:
                        s = dict(s)
                        state_id = s.get("state_id")
                        if not state_id and s.get("name"):
                            state_id, _ = resolve_state_name(
                                s["name"],
                                country_id=node.get("country_id")
                                or (node.get("country") or {}).get("country_id"),
                            )
                        if not state_id:
                            label = s.get("name") or "<?>"
                            raise ValueError(
                                f"state_in: state not found '{label}' (index {index_for_errors})"
                            )
                        state_ids.append(state_id)
                    if state_ids:
                        node["state_ids"] = list(dict.fromkeys(state_ids))  # dedup
                    # keep 'states' and/or 'state_names' for GET readability

                # recurse
                for key, val in list(node.items()):
                    node[key] = _norm(val)
                return node

            if isinstance(node, list):
                return [_norm(x) for x in node]
            return node

        expr_dict = expr.model_dump(by_alias=True)
        normalized = _norm(expr_dict)
        return TypeAdapter(TE).validate_python(normalized)

    @staticmethod
    def legacy_fixup_expression(exp: Any) -> Any:
        """Adapt old short forms to the canonical form.

        FUNCTION IDENTICAL TO THE ORIGINAL _legacy_fixup_expression.

        Description:
            E.g.: `type_in.codes -> type_in.types[{cache_type_code}]`,
            `size_in.codes -> size_in.sizes[{code}]`.

        Args:
            exp: Raw expression.

        Returns:
            Any: Non-destructively transformed expression.
        """

        def _fix(node: Any) -> Any:
            if isinstance(node, dict):
                k = node.get("kind")

                # type_in: { codes: [...] } -> { types: [{cache_type_code: ...}, ...] }
                if k == "type_in" and "codes" in node and "types" not in node:
                    node = {**node}
                    node["types"] = [{"cache_type_code": c} for c in node.pop("codes")]

                # size_in: { codes: [...] } -> { sizes: [{code: ...}, ...] }
                if k == "size_in" and "codes" in node and "sizes" not in node:
                    node = {**node}
                    node["sizes"] = [{"code": c} for c in node.pop("codes")]

                # recurse into children
                for kk, vv in list(node.items()):
                    node[kk] = _fix(vv)
                return node

            if isinstance(node, list):
                return [_fix(x) for x in node]
            return node

        return _fix(exp)
