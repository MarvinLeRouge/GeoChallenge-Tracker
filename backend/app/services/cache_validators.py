"""
Validation service for cache data.

This module contains validation logic separated from processing logic
to follow the single responsibility principle.
"""

from typing import Any


def _validate_coordinates(item: dict[str, Any]) -> dict[str, Any] | None:
    """Validate that `item` has valid lat/lon coordinates.

    Args:
        item: The cache item to validate.

    Returns:
        dict | None: An invalid-result dict, or None if coordinates are valid.
    """
    lat = item.get("latitude")
    lon = item.get("longitude")
    if lat is None or lon is None:
        return {"is_valid": False, "reason": "missing_coordinates"}

    try:
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return {"is_valid": False, "reason": "invalid_coordinates_range"}
    except (TypeError, ValueError):
        return {"is_valid": False, "reason": "invalid_coordinate_values"}

    return None


def _validate_cache_type(item: dict[str, Any], all_types_by_name: dict) -> dict[str, Any] | None:
    """Validate that `item`'s cache type resolves to a known, existing type.

    Args:
        item: The cache item to validate.
        all_types_by_name: Cached lookup for types.

    Returns:
        dict | None: An invalid-result dict, or None if the type is valid.
    """
    type_name = item.get("cache_type")
    # Need to import the type lookup function from its new location
    from app.services.type_helpers import get_type_by_name

    type_id = get_type_by_name(type_name, all_types_by_name)  # Using the existing function
    if type_id is None:
        # Try to resolve using the referential cache
        from app.services.referentials_cache import resolve_type_code

        resolved_type_id = resolve_type_code(type_name) if type_name else None
        if resolved_type_id is None:
            return {"is_valid": False, "reason": f"unknown_cache_type: {type_name}"}
    else:
        # Verify that the resolved type_id exists in the DB
        from app.services.referentials_cache import exists_id

        if not exists_id("cache_types", type_id):
            return {"is_valid": False, "reason": f"cache_type_not_in_db: {type_name}"}

    return None


def _validate_cache_size(item: dict[str, Any], all_sizes_by_name: dict) -> dict[str, Any] | None:
    """Validate that `item`'s cache size resolves to a known, existing size.

    Args:
        item: The cache item to validate.
        all_sizes_by_name: Cached lookup for sizes.

    Returns:
        dict | None: An invalid-result dict, or None if the size is valid.
    """
    size_name = item.get("cache_size")
    # Need to import the size lookup function from its new location
    from app.services.size_helpers import get_size_by_name

    size_id = get_size_by_name(size_name, all_sizes_by_name)  # Using the existing function
    if size_id is None:
        # Try to resolve using the referential cache
        from app.services.referentials_cache import resolve_size_code, resolve_size_name

        resolved_size_id = resolve_size_code(size_name) if size_name else None
        if resolved_size_id is None:
            resolved_size_id = resolve_size_name(size_name) if size_name else None
        if resolved_size_id is None:
            return {"is_valid": False, "reason": f"unknown_cache_size: {size_name}"}
    else:
        # Verify that the resolved size_id exists in the DB
        from app.services.referentials_cache import exists_id

        if not exists_id("cache_sizes", size_id):
            return {"is_valid": False, "reason": f"cache_size_not_in_db: {size_name}"}

    return None


def _validate_dt_value(value_str: Any, label: str) -> dict[str, Any] | None:
    """Validate a difficulty/terrain value: range 1.0 to 5.0 in 0.5 increments.

    Args:
        value_str: Raw difficulty/terrain value (often a string, possibly empty).
        label: "difficulty" or "terrain", used to build the reason codes.

    Returns:
        dict | None: An invalid-result dict, or None if the value is valid (or empty).
    """
    try:
        value = float(value_str) if value_str != "" else None
        if value is not None:
            if not (1.0 <= value <= 5.0):
                return {"is_valid": False, "reason": f"{label}_out_of_range: {value}"}
            # Check for valid 0.5 increments (e.g., 1.0, 1.5, 2.0, ..., 5.0)
            if round(value * 2) != value * 2:
                return {"is_valid": False, "reason": f"{label}_invalid_increment: {value}"}
    except (TypeError, ValueError):
        if value_str != "":  # Only error if not empty
            return {"is_valid": False, "reason": f"{label}_invalid_value: {value_str}"}

    return None


async def validate_cache_comprehensive(
    item: dict[str, Any], all_types_by_name: dict, all_sizes_by_name: dict
) -> dict[str, Any]:
    """
    Validator for comprehensive cache validation.

    Validates:
    - lat/lon existence and validity
    - type_id and size_id existence in collections
    - difficulty and terrain in valid range (1.0 to 5.0 in 0.5 increments)

    Args:
        item: The cache item to validate
        all_types_by_name: Cached lookup for types
        all_sizes_by_name: Cached lookup for sizes

    Returns:
        dict: {"is_valid": bool, "reason": str}
    """
    error = _validate_coordinates(item)
    if error:
        return error

    error = _validate_cache_type(item, all_types_by_name)
    if error:
        return error

    error = _validate_cache_size(item, all_sizes_by_name)
    if error:
        return error

    error = _validate_dt_value(item.get("difficulty", ""), "difficulty")
    if error:
        return error

    error = _validate_dt_value(item.get("terrain", ""), "terrain")
    if error:
        return error

    return {"is_valid": True, "reason": "valid"}
