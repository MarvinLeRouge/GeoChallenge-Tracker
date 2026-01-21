# backend/app/services/location_parser.py
# Utilitaires de parsing et formatage de coordonnées (DD/DM/DMS).

from __future__ import annotations

import re


def normalize_location_string(s: str) -> str:
    """Normaliser une chaine de coordonnees.

    Description:
        Unifie decimales (virgule->point), symboles et espaces.

    Args:
        s: Chaine brute.

    Returns:
        str: Chaine normalisee.
    """
    s = s.strip()
    # virgule decimale -> point
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # normaliser symboles unicode
    s = s.replace("'", "'").replace('"', '"').replace('"', '"')
    # compacter espaces multiples
    s = re.sub(r"\s+", " ", s)
    return s


# Un composant (lat OU lon) : [NSEW]? [+/-]? d [m [s]]
# ° ' " optionnels; hémisphère possible en préfixe ou suffixe
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
    """Convertir degres/minutes/secondes en degres decimaux.

    Args:
        d: Degres.
        m: Minutes (0-<60) ou None.
        s: Secondes (0-<60) ou None.

    Returns:
        float: Valeur en degres decimaux.

    Raises:
        ValueError: Minutes/secondes hors bornes.
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
    """Transformer un composant regex en (valeur, hémisphère, signe).

    Args:
        match: Résultat du motif `_LOCATION_COMP`.

    Returns:
        tuple: `(degres_signés, hem_NSEW|None, raw_sign in {+1,-1})`.
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
    """Appliquer la règle de signe en fonction de l'hémisphère.

    Description:
        Le signe numérique explicite prime ; sinon N/S règle la latitude, E/W la longitude.

    Args:
        value: Valeur absolue en degrés.
        hem: Hémisphère détectée (N/S/E/W) ou None.
        is_latitude: True si la valeur représente une latitude.

    Returns:
        float: Valeur signée cohérente.
    """
    if value < 0:
        return value  # signe explicite -> priorité
    if hem:
        if is_latitude:  # lat
            if hem == "S":
                return -abs(value)
            # N ou autre -> positif
            return abs(value)
        else:  # lon
            if hem == "W":
                return -abs(value)
            return abs(value)
    # pas de hem, pas de signe -> par défaut N/E donc positif
    return abs(value)


def parse_location_to_lon_lat(position: str) -> tuple[float, float]:
    """Parser une position libre vers (lon, lat).

    Description:
        Accepte formats DD/DM/DMS mixtes ; si hémisphères présents aux deux composants,
        l'ordre est déduit ; sinon on suppose (lat, lon).

    Args:
        position: Chaîne de coordonnées.

    Returns:
        tuple[float, float]: (longitude, latitude).

    Raises:
        ValueError: Parsing impossible ou coordonnées hors bornes.
    """
    txt = normalize_location_string(position)
    # Extraire deux composants
    matches = list(_LOCATION_COMP.finditer(txt))
    if len(matches) < 2:
        # Tentative: formats "dd, dd" simples (ex: "50.1, 5.2")
        m = re.findall(r"[-+]?\d+(?:\.\d+)?", txt)
        if len(m) >= 2:
            lat = float(m[0])
            lon = float(m[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("coordinates out of range")
            return (lon, lat)
        raise ValueError("unable to parse position")

    # Convertir les deux premières occurrences
    v1, hem1, _ = _parse_location_component(matches[0])
    v2, hem2, _ = _parse_location_component(matches[1])

    # Déterminer quel est lat vs lon
    # Cas où hémisphères présents et distincts -> on s'appuie dessus
    if hem1 in ("N", "S") and hem2 in ("E", "W"):
        lat = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=True)
        lon = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=False)
        return (lon, lat)
    if hem1 in ("E", "W") and hem2 in ("N", "S"):
        lon = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=False)
        lat = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=True)
        return (lon, lat)

    # Sinon, on suppose l'ordre (lat, lon)
    lat = _resolve_hemisphere_sign(abs(v1), hem1, is_latitude=True)
    lon = _resolve_hemisphere_sign(abs(v2), hem2, is_latitude=False)

    # Validations finales
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates out of range")
    return (lon, lat)


def format_decimal_to_deg_min_mil(decimal_coord: float) -> str:
    """Convertir un degre decimal vers degres minutes.mmm.

    Args:
        decimal_coord: Coordonnee decimale (ex. 43.123456).

    Returns:
        str: Forme ±DD MM.mmm.
    """
    # Garder le signe
    sign = "-" if decimal_coord < 0 else "+"
    abs_coord = abs(decimal_coord)

    # Partie entiere = degres
    degrees = int(abs_coord)

    # Partie decimale * 60 = minutes
    minutes = (abs_coord - degrees) * 60

    # Format: DD MM.mmm (3 décimales pour les minutes)
    return f"{sign}{degrees} {minutes:06.3f}"


def format_coordinates_deg_min_mil(lat: float, lon: float) -> str:
    """Formatter (lat, lon) en N/S DD MM.mmm  E/O DD MM.mmm.

    Args:
        lat: Latitude decimale.
        lon: Longitude decimale.

    Returns:
        str: Chaine formatee (ex. N43 07.407 E005 23.456).
    """
    lat_str = format_decimal_to_deg_min_mil(lat)
    lat_str = lat_str.replace("+", "N")
    lat_str = lat_str.replace("-", "S")
    lon_str = format_decimal_to_deg_min_mil(lon)
    lon_str = lon_str.replace("+", "E")
    lon_str = lon_str.replace("-", "W")
    result = f"{lat_str} {lon_str}"

    return result
