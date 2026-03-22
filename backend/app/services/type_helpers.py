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
    type_id: ObjectId | None = None
    if isinstance(all_types_by_name, dict):
        type_id = all_types_by_name.get(cache_type_name, None)
    if type_id is None:
        if isinstance(all_types_by_name, dict):
            for db_name, db_id in all_types_by_name.items():
                if db_name in cache_type_name or cache_type_name in db_name:
                    type_id = db_id
                    break
    if type_id is None:
        for key, label in synonymes.items():
            if key in cache_type_name:
                if isinstance(all_types_by_name, dict):
                    for db_name, db_id in all_types_by_name.items():
                        if label in db_name:
                            type_id = db_id
                            break
                if type_id is not None:
                    break

    return type_id
