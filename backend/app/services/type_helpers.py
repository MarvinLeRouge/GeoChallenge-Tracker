"""
Type lookup helpers.

Separated from processing logic to improve testability and maintainability.
"""

from bson import ObjectId


def _normalize_name(name: str | None) -> str:
    """Normalize a label for referential matching.

    Description:
        Strips and applies `casefold()` for case-insensitive comparisons (e.g. "micro" vs "Micro").

    Args:
        name (str | None): Source label.

    Returns:
        str: Normalized label (possibly an empty string).
    """
    return (name or "").strip().casefold()


def _exact_match_type_id(
    cache_type_name: str, all_types_by_name: dict[str, ObjectId] | None
) -> ObjectId | None:
    """Resolve by exact normalized-name match.

    Args:
        cache_type_name: Normalized type name.
        all_types_by_name: Index `{name_normalized: _id}`.

    Returns:
        ObjectId | None: Matched type id, if any.
    """
    if isinstance(all_types_by_name, dict):
        return all_types_by_name.get(cache_type_name, None)
    return None


def _substring_match_type_id(
    cache_type_name: str, all_types_by_name: dict[str, ObjectId] | None
) -> ObjectId | None:
    """Resolve by substring match (either direction) against known type names.

    Args:
        cache_type_name: Normalized type name.
        all_types_by_name: Index `{name_normalized: _id}`.

    Returns:
        ObjectId | None: Matched type id, if any.
    """
    if not isinstance(all_types_by_name, dict):
        return None
    for db_name, db_id in all_types_by_name.items():
        if db_name in cache_type_name or cache_type_name in db_name:
            return db_id
    return None


def _synonym_match_type_id(
    cache_type_name: str,
    all_types_by_name: dict[str, ObjectId] | None,
    synonymes: dict[str, str],
) -> ObjectId | None:
    """Resolve via a known synonym whose label appears in a known type name.

    Args:
        cache_type_name: Normalized type name.
        all_types_by_name: Index `{name_normalized: _id}`.
        synonymes: `{synonym_key: label}` mapping.

    Returns:
        ObjectId | None: Matched type id, if any.
    """
    if not isinstance(all_types_by_name, dict):
        return None
    for key, label in synonymes.items():
        if key not in cache_type_name:
            continue
        for db_name, db_id in all_types_by_name.items():
            if label in db_name:
                return db_id
    return None


def get_type_by_name(
    cache_type_name: str | None,
    all_types_by_name: dict[str, ObjectId] | None = None,
):
    """Resolve a cache type by name (with synonym support).

    Args:
        cache_type_name (str | None): Type label (e.g. "Traditional").
        all_types_by_name (dict | None): Index `{name_normalized: _id}` (recommended).

    Returns:
        ObjectId | None: Type reference if resolved.
    """
    synonymes = {
        "unknown": "mystery",
    }

    cache_type_name = _normalize_name(cache_type_name)

    type_id = _exact_match_type_id(cache_type_name, all_types_by_name)
    if type_id is None:
        type_id = _substring_match_type_id(cache_type_name, all_types_by_name)
    if type_id is None:
        type_id = _synonym_match_type_id(cache_type_name, all_types_by_name, synonymes)

    return type_id
