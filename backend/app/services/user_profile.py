# backend/app/services/user_profile.py
# Parse des coordonnées (formats DD/DM/DMS), conversion, lecture/écriture en base (GeoJSON Point).

from __future__ import annotations
from bson import ObjectId
import re
from datetime import datetime
from math import floor
from app.core.utils import *
from app.db.mongodb import get_collection

# --- PARSEUR POSITION (DD / DM / DMS) --------------------------------------

# Normalise les symboles (prime/second), espaces, décimales
def _location_norm(s: str) -> str:
    """Normaliser une chaîne de coordonnées.

    Description:
        Unifie décimales (virgule→point), symboles (′″→'") et espaces.

    Args:
        s: Chaîne brute.

    Returns:
        str: Chaîne normalisée.
    """
    s = s.strip()
    # virgule décimale -> point
    s = re.sub(r'(\d),(\d)', r'\1.\2', s)
    # normaliser symboles unicode
    s = s.replace("′", "'").replace("”", '"').replace("″", '"')
    # compacter espaces multiples
    s = re.sub(r'\s+', ' ', s)
    return s

# Un composant (lat OU lon) : [NSEW]? [+/-]? d [m [s]]
# ° ' " optionnels; hémisphère possible en préfixe ou suffixe
_LOCATION_COMP = re.compile(
    r"""
    (?P<prefix_hem>[NnSsEeWw])?\s*
    (?P<sign>[+-])?\s*
    (?P<deg>\d+(?:\.\d+)?)
    (?:\s*[°\s]\s*
        (?P<min>\d+(?:\.\d+)?)
        (?:\s*['\s]\s*
            (?P<sec>\d+(?:\.\d+)?)
            \s*(?:["])?
        )?
    )?
    \s*(?P<suffix_hem>[NnSsEeWw])?
    """,
    re.VERBOSE,
)

def _location_to_degrees(d: float, m: float | None, s: float | None) -> float:
    """Convertir degrés/minutes/secondes en degrés décimaux.

    Args:
        d: Degrés.
        m: Minutes (0–<60) ou None.
        s: Secondes (0–<60) ou None.

    Returns:
        float: Valeur en degrés décimaux.

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

def _location_component_to_deg(match: re.Match) -> tuple[float, str | None, int]:
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
    val = _location_to_degrees(deg, min_, sec_)
    hem = (g.get("prefix_hem") or g.get("suffix_hem") or "").upper() or None
    raw_sign = -1 if g.get("sign") == "-" else 1
    return (val * raw_sign, hem, raw_sign)

def _location_resolve_sign(value: float, hem: str | None, is_lat_guess: bool) -> float:
    """Appliquer la règle de signe en fonction de l’hémisphère.

    Description:
        Le signe numérique explicite prime ; sinon N/S règle la latitude, E/W la longitude.

    Args:
        value: Valeur absolue en degrés.
        hem: Hémisphère détectée (N/S/E/W) ou None.
        is_lat_guess: True si la valeur représente une latitude.

    Returns:
        float: Valeur signée cohérente.
    """
    if value < 0:
        return value  # signe explicite -> priorité
    if hem:
        if is_lat_guess:  # lat
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

def location_parse_to_lon_lat(position: str) -> tuple[float, float]:
    """Parser une position libre vers (lon, lat).

    Description:
        Accepte formats DD/DM/DMS mixtes ; si hémisphères présents aux deux composants,
        l’ordre est déduit ; sinon on suppose (lat, lon).

    Args:
        position: Chaîne de coordonnées.

    Returns:
        tuple[float, float]: (longitude, latitude).

    Raises:
        ValueError: Parsing impossible ou coordonnées hors bornes.
    """
    txt = _location_norm(position)
    # Extraire deux composants
    matches = list(_LOCATION_COMP.finditer(txt))
    if len(matches) < 2:
        # Tentative: formats "dd, dd" simples (ex: "50.1, 5.2")
        m = re.findall(r'[-+]?\d+(?:\.\d+)?', txt)
        if len(m) >= 2:
            lat = float(m[0])
            lon = float(m[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("coordinates out of range")
            return (lon, lat)
        raise ValueError("unable to parse position")

    # Convertir les deux premières occurrences
    v1, hem1, _ = _location_component_to_deg(matches[0])
    v2, hem2, _ = _location_component_to_deg(matches[1])

    # Déterminer quel est lat vs lon
    # Cas où hémisphères présents et distincts -> on s'appuie dessus
    if hem1 in ("N", "S") and hem2 in ("E", "W"):
        lat = _location_resolve_sign(abs(v1), hem1, is_lat_guess=True)
        lon = _location_resolve_sign(abs(v2), hem2, is_lat_guess=False)
        return (lon, lat)
    if hem1 in ("E", "W") and hem2 in ("N", "S"):
        lon = _location_resolve_sign(abs(v1), hem1, is_lat_guess=False)
        lat = _location_resolve_sign(abs(v2), hem2, is_lat_guess=True)
        return (lon, lat)

    # Sinon, on suppose l'ordre (lat, lon)
    lat = _location_resolve_sign(abs(v1), hem1, is_lat_guess=True)
    lon = _location_resolve_sign(abs(v2), hem2, is_lat_guess=False)

    # Validations finales
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates out of range")
    return (lon, lat)

def user_location_get(user_id: ObjectId):
    """Lire la localisation (GeoJSON) de l’utilisateur.

    Args:
        user_id: Identifiant utilisateur.

    Returns:
        dict | None: Champ `location` (GeoJSON Point) ou None.
    """
    doc = get_collection("users").find_one({"_id": user_id}, {"_id": 1, "location": 1})
    
    return (doc or {}).get("location")    

def user_location_set(user_id: ObjectId, lon: float, lat: float):
    """Écrire la localisation utilisateur (GeoJSON Point).

    Args:
        user_id: Identifiant utilisateur.
        lon: Longitude (−180..180).
        lat: Latitude (−90..90).

    Returns:
        UpdateResult: Résultat MongoDB (ack/modified).
    """
    result = get_collection("users").update_one(
        {"_id": user_id},
        {"$set": {
            "location": {
                "type": "Point",
                "coordinates": [lon, lat],
                "updated_at": utcnow()
            }
        }})

    return result

def degrees_to_deg_min_mil(decimal_coord: float) -> str:
    """Convertir un degré décimal vers « degrés minutes.mmm ».

    Args:
        decimal_coord: Coordonnée décimale (ex. 43.123456).

    Returns:
        str: Forme `±DD MM.mmm`.
    """
    # Garder le signe
    sign = "-" if decimal_coord < 0 else "+"
    abs_coord = abs(decimal_coord)
    
    # Partie entière = degrés
    degrees = int(abs_coord)
    
    # Partie décimale * 60 = minutes
    minutes = (abs_coord - degrees) * 60
    
    # Format: DD MM.mmm (3 décimales pour les minutes)
    return f"{sign}{degrees} {minutes:06.3f}"

def coords_in_deg_min_mil(lat: float, lon: float) -> str:
    """Formatter `(lat, lon)` en « N/S DD MM.mmm  E/O DD MM.mmm ».

    Args:
        lat: Latitude décimale.
        lon: Longitude décimale.

    Returns:
        str: Chaîne formatée (ex. `N43 07.407 E005 23.456`).
    """
    lat_str = degrees_to_deg_min_mil(lat)
    lat_str = lat_str.replace("+", "N")
    lat_str = lat_str.replace("-", "S")
    lon_str = degrees_to_deg_min_mil(lon)
    lon_str = lon_str.replace("+", "E")
    lon_str = lon_str.replace("-", "W")
    result = f"{lat_str} {lon_str}"

    return result