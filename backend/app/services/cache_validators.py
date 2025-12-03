"""
Validation service for cache data.

This module contains validation logic separated from processing logic
to follow the single responsibility principle.
"""

from typing import Dict, Any
from bson import ObjectId


async def validate_cache_comprehensive(item: Dict[str, Any], all_types_by_name: Dict, all_sizes_by_name: Dict) -> Dict[str, Any]:
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
    # Validate coordinates exist and are valid
    lat = item.get("latitude")
    lon = item.get("longitude")
    if lat is None or lon is None:
        return {"is_valid": False, "reason": "missing_coordinates"}

    # Validate coordinates are valid numbers
    try:
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return {"is_valid": False, "reason": "invalid_coordinates_range"}
    except (TypeError, ValueError):
        return {"is_valid": False, "reason": "invalid_coordinate_values"}

    # Validate type_id exists in cache_types collection
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

    # Validate size_id exists in cache_sizes collection
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

    # Validate difficulty and terrain are in range 1.0 to 5.0 with 0.5 increments
    difficulty_str = item.get("difficulty", "")
    terrain_str = item.get("terrain", "")

    try:
        difficulty = float(difficulty_str) if difficulty_str != "" else None
        if difficulty is not None:
            if not (1.0 <= difficulty <= 5.0):
                return {"is_valid": False, "reason": f"difficulty_out_of_range: {difficulty}"}
            # Check for valid 0.5 increments (e.g., 1.0, 1.5, 2.0, ..., 5.0)
            if round(difficulty * 2) != difficulty * 2:
                return {"is_valid": False, "reason": f"difficulty_invalid_increment: {difficulty}"}
    except (TypeError, ValueError):
        if difficulty_str != "":  # Only error if not empty
            return {"is_valid": False, "reason": f"difficulty_invalid_value: {difficulty_str}"}

    try:
        terrain = float(terrain_str) if terrain_str != "" else None
        if terrain is not None:
            if not (1.0 <= terrain <= 5.0):
                return {"is_valid": False, "reason": f"terrain_out_of_range: {terrain}"}
            # Check for valid 0.5 increments (e.g., 1.0, 1.5, 2.0, ..., 5.0)
            if round(terrain * 2) != terrain * 2:
                return {"is_valid": False, "reason": f"terrain_invalid_increment: {terrain}"}
    except (TypeError, ValueError):
        if terrain_str != "":  # Only error if not empty
            return {"is_valid": False, "reason": f"terrain_invalid_value: {terrain_str}"}

    # If all validations pass
    return {"is_valid": True, "reason": "valid"}