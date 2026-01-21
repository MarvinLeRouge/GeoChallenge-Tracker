"""
Size lookup helpers.

Separated from processing logic to improve testability and maintainability.
"""

from bson import ObjectId


def _normalize_name(name: str | None) -> str:
    """Normaliser un libellé pour matching référentiel.

    Description:
        Trim et `casefold()` pour des comparaisons tolérantes (ex. « micro » vs « Micro »).

    Args:
        name (str | None): Libellé source.

    Returns:
        str: Libellé normalisé (éventuellement chaîne vide).
    """
    return (name or "").strip().casefold()


def get_size_by_name(
    cache_size_name: str | None,
    all_sizes_by_name: dict[str, ObjectId] | None = None,
):
    """Résoudre la taille par nom.

    Description:
        Similarité avec `get_type_by_name` : exact puis partiel, retourne l’ObjectId ou None.

    Args:
        cache_size_name (str | None): Libellé taille (ex. "Micro").
        all_sizes_by_name (dict | None): Index `{name_normalized: _id}`.

    Returns:
        ObjectId | None: Référence de la taille si résolue.
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
