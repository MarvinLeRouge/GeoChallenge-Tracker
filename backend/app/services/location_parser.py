# backend/app/services/location_parser.py
# Utilities for parsing and formatting coordinates (DD/DM/DMS).

from __future__ import annotations

import re


def normalize_location_string(s: str) -> str:
    """Normalize a coordinate string.

    Description:
        Unifies decimal separators (comma->period), symbols, and whitespace.

    Args:
        s: Raw coordinate string.

    Returns:
        str: Normalized string.
    """
    s = s.strip()
    # decimal comma -> period
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # normalize unicode symbols
    s = s.replace("'", "'").replace('"', '"').replace('"', '"')
    # collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    return s


# One component (lat OR lon): [NSEW]? [+/-]? d [m [s]]
# °, ', " optional; hemisphere may appear as prefix or suffix
_LOCATION_COMP = re.compile(
    r"(?P<prefix_hem>[NnSsEeWw])?\s*"
    r"(?P<sign>[+-])?\s*"
    r"(?P<deg>\d+(?:\.\d+)?)"
    r"(?:\s*[°\s]\s*"
    r"(?P<min>\d+(?:\.\d+)?)"
    r"(?:\s*['\s]\s*"
    r"(?P<sec>\d+(?:\.\d+)?)"
    r"\s*(?:[\"]))?"
    r")?"
    r"\s*(?P<suffix_hem>[NnSsEeWw])?",
    re.VERBOSE,
)


def _degrees_minutes_seconds_to_decimal(d: float, m: float | None, s: float | None) -> float:
    """Convert degrees/minutes/seconds to decimal degrees.

    Args:
        d: Degrees.
        m: Minutes (0–<60) or None.
        s: Seconds (0–<60) or None.

    Returns:
        float: Value in decimal degrees.

    Raises:
        ValueError: Minutes or seconds out of range.
    """
    val = float(d)
    if m is not None:
        if not (0 <= m < 60):
            raise ValueError("minutes out of range")
        val += float(m) / 60.0
    if s is not None:
        if not (0 <= s < 60):
            raise ValueError("seconds out of range")
        val += float(s) / 3600.0
    return val


def _parse_location_component(match: re.Match) -> tuple[float, str | None, int]:
    """Transform a regex component match into (value, hemisphere, sign).

    Args:
        match: Result of the `_LOCATION_COMP` pattern.

    Returns:
        tuple: `(signed_degrees, hem_NSEW|None, raw_sign in {+1,-1})`.
    """
    g = match.groupdict()
    deg = float(g["deg"])
    min_ = float(g["min"]) if g.get("min") else None
    sec_ = float(g["sec"]) if g.get("sec") else None
    val = _degrees_minutes_seconds_to_decimal(deg, min_, sec_)
    hem = (g.get("prefix_hem") or g.get("suffix_hem") or "").upper() or None
    raw_sign = -1 if g.get("sign") == "-" else 1
    return (val * raw_sign, hem, raw_sign)


def _resolve_hemisphere_sign(value: float, hem: str | None, is_latitude: bool) -> float:
    """Apply sign rule based on hemisphere indicator.

    Description:
        An explicit numeric sign takes precedence; otherwise N/S governs latitude and E/W governs longitude.

    Args:
        value: Absolute value in degrees.
        hem: Detected hemisphere (N/S/E/W) or None.
        is_latitude: True if the value represents a latitude.

    Returns:
        float: Consistently signed value.
    """
    if value < 0:
        return value  # explicit sign -> takes precedence
    if hem:
        if is_latitude:  # lat
            if hem == "S":
                return -abs(value)
            # N or other -> positive
            return abs(value)
        else:  # lon
            if hem == "W":
                return -abs(value)
            return abs(value)
    # no hemisphere, no sign -> defaults to N/E, therefore positive
    return abs(value)


def parse_location_to_lon_lat(position: str) -> tuple[float, float]:
    """Parse a free-form position string to (lon, lat).

    Description:
        Accepts mixed DD/DM/DMS formats; if hemispheres are present on both components,
        the order is inferred from them; otherwise (lat, lon) order is assumed.

    Args:
        position: Coordinate string.

    Returns:
        tuple[float, float]: (longitude, latitude).

    Raises:
        ValueError: If parsing fails or coordinates are out of range.
    """
    txt = normalize_location_string(position)
    # Extract two components
    matches = list(_LOCATION_COMP.finditer(txt))
    if len(matches) < 2:
        # Fallback: simple "dd, dd" formats (e.g. "50.1, 5.2")
        m = re.findall(r"[-+]?\d+(?:\.\d+)?", txt)
        if len(m) >= 2:
            lat = float(m[0])
            lon = float(m[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("coordinates out of range")
            return (lon, lat)
        raise ValueError("unable to parse position")

    # Convert the first two matches
    v1, hem1, _ = _parse_location_component(matches[0])
    v2, hem2, _ = _parse_location_component(matches[1])

    # Determine which is lat vs lon
    # When both hemispheres are present and distinct, rely on them
    if hem1 in ("N", "S") and hem2 in ("E", "W"):
        lat = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=True)
        lon = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=False)
        return (lon, lat)
    if hem1 in ("E", "W") and hem2 in ("N", "S"):
        lon = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=False)
        lat = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=True)
        return (lon, lat)

    # Otherwise, assume (lat, lon) order
    lat = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=True)
    lon = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=False)

    # Final validation
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates out of range")
    return (lon, lat)


def format_decimal_to_deg_min_mil(decimal_coord: float) -> str:
    """Convert a decimal degree value to degrees minutes.mmm.

    Args:
        decimal_coord: Decimal coordinate (e.g. 43.123456).

    Returns:
        str: Form ±DD MM.mmm.
    """
    # Preserve sign
    sign = "-" if decimal_coord < 0 else "+"
    abs_coord = abs(decimal_coord)

    # Integer part = degrees
    degrees = int(abs_coord)

    # Decimal part * 60 = minutes
    minutes = (abs_coord - degrees) * 60

    # Format: DD MM.mmm (3 decimal places for minutes)
    return f"{sign}{degrees} {minutes:06.3f}"


def format_coordinates_deg_min_mil(lat: float, lon: float) -> str:
    """Format (lat, lon) as N/S DD MM.mmm  E/W DD MM.mmm.

    Args:
        lat: Decimal latitude.
        lon: Decimal longitude.

    Returns:
        str: Formatted string (e.g. N43 07.407 E005 23.456).
    """
    lat_str = format_decimal_to_deg_min_mil(lat)
    lat_str = lat_str.replace("+", "N")
    lat_str = lat_str.replace("-", "S")
    lon_str = format_decimal_to_deg_min_mil(lon)
    lon_str = lon_str.replace("+", "E")
    lon_str = lon_str.replace("-", "W")
    result = f"{lat_str} {lon_str}"

    return result
