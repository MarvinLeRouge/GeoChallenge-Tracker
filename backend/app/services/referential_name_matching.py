"""Shared label-normalization helper for referential name matching.

Used by both size_helpers.py and type_helpers.py to normalize a cache
size/type label before exact/substring matching against the known
referential names.
"""


def normalize_referential_name(name: str | None) -> str:
    """Normalize a label for referential matching.

    Description:
        Strips and applies `casefold()` for case-insensitive comparisons (e.g. "micro" vs "Micro").

    Args:
        name (str | None): Source label.

    Returns:
        str: Normalized label (possibly an empty string).
    """
    return (name or "").strip().casefold()
