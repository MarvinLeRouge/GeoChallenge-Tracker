"""
Size lookup helpers.

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


def get_size_by_name(
    cache_size_name: str | None,
    all_sizes_by_name: dict[str, ObjectId] | None = None,
):
    """Resolve a cache size by name.

    Description:
        Similar to `get_type_by_name`: exact match first, then partial; returns ObjectId or None.

    Args:
        cache_size_name (str | None): Size label (e.g. "Micro").
        all_sizes_by_name (dict | None): Index `{name_normalized: _id}`.

    Returns:
        ObjectId | None: Size reference if resolved.
    """
    cache_size_name = _normalize_name(cache_size_name)
    size_id: ObjectId | None = None
    if isinstance(all_sizes_by_name, dict):
        size_id = all_sizes_by_name.get(cache_size_name, None)
    if size_id is None:
        if isinstance(all_sizes_by_name, dict):
            for db_name, db_id in all_sizes_by_name.items():
                if db_name in cache_size_name or cache_size_name in db_name:
                    size_id = db_id
                    break

    return size_id
