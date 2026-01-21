# backend/app/services/gpx_import/data_normalizer.py
# Normalisation et parsing des données GPX.

from __future__ import annotations

import datetime as dt
import re
from typing import Any


class DataNormalizer:
    """Service de normalisation des données GPX.

    Description:
        Responsable du parsing et de la normalisation des données
        extraites des fichiers GPX (dates, coordonnées, types, etc.).
    """

    @staticmethod
    def normalize_name(name: str | None) -> str:
        """Normaliser un nom (référentiels, noms de fichiers, etc.).

        Args:
            name: Nom à normaliser.

        Returns:
            str: Nom normalisé.
        """
        if not name:
            return ""

        # Garder uniquement les caractères alphanumériques
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        return normalized

    @staticmethod
    def parse_datetime_iso8601(date_str: str | None) -> dt.datetime | None:
        """Parser une date au format ISO8601.

        Args:
            date_str: Chaîne de date à parser.

        Returns:
            datetime | None: Date parsée ou None si échec.
        """
        if not date_str:
            return None

        # Formats supportés
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2023-05-15T14:30:45.123Z
            "%Y-%m-%dT%H:%M:%SZ",  # 2023-05-15T14:30:45Z
            "%Y-%m-%dT%H:%M:%S.%f",  # 2023-05-15T14:30:45.123
            "%Y-%m-%dT%H:%M:%S",  # 2023-05-15T14:30:45
            "%Y-%m-%d %H:%M:%S",  # 2023-05-15 14:30:45
            "%Y-%m-%d",  # 2023-05-15
        ]

        # Nettoyer la chaîne
        date_str = date_str.strip()

        # Essayer les différents formats
        for fmt in formats:
            try:
                return dt.datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Tentative avec parsing manuel pour les formats non standard
        try:
            # Supprimer les millisecondes si présentes
            if "." in date_str and date_str.endswith("Z"):
                date_str = date_str.split(".")[0] + "Z"

            # Parser avec dateutil si disponible
            from dateutil import parser

            return parser.parse(date_str)
        except (ImportError, ValueError):
            pass

        return None

    @staticmethod
    def normalize_coordinates(
        lat: str | float | None, lon: str | float | None
    ) -> tuple[float | None, float | None]:
        """Normaliser et valider des coordonnées.

        Args:
            lat: Latitude (string ou float).
            lon: Longitude (string ou float).

        Returns:
            tuple: (latitude, longitude) normalisées ou (None, None).
        """
        try:
            if lat is None or lon is None:
                return None, None

            # Conversion en float
            lat_float = float(lat)
            lon_float = float(lon)

            # Validation des bornes
            if not (-90 <= lat_float <= 90):
                return None, None
            if not (-180 <= lon_float <= 180):
                return None, None

            return lat_float, lon_float

        except (ValueError, TypeError):
            return None, None

    @staticmethod
    def normalize_difficulty_terrain(value: str | float | None) -> float | None:
        """Normaliser une valeur de difficulté ou terrain.

        Args:
            value: Valeur à normaliser.

        Returns:
            float | None: Valeur entre 1.0 et 5.0 ou None.
        """
        if value is None:
            return None

        try:
            float_val = float(value)

            # Validation des bornes
            if not (1.0 <= float_val <= 5.0):
                return None

            # Arrondir à 0.5
            return round(float_val * 2) / 2.0

        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_gc_code(gc_code: str | None) -> str | None:
        """Normaliser un code GC.

        Args:
            gc_code: Code GC brut.

        Returns:
            str | None: Code GC normalisé ou None.
        """
        if not gc_code:
            return None

        # Nettoyer et mettre en majuscules
        cleaned = gc_code.strip().upper()

        # Valider le format GCxxxxx
        if not re.match(r"^GC[A-Z0-9]+$", cleaned):
            return None

        return cleaned

    @staticmethod
    def is_valid_for_import_mode(cache_data: dict[str, Any], import_mode: str) -> bool:
        """Vérifier si une cache est valide pour le mode d'import.

        Args:
            cache_data: Données de la cache.
            import_mode: Mode d'import ('found', 'caches', 'both').

        Returns:
            bool: True si la cache doit être importée.
        """
        # Toujours importer si mode 'both'
        if import_mode == "both":
            return True

        # Pour mode 'found', vérifier qu'il y a une date de trouvaille
        if import_mode == "found":
            return cache_data.get("found_date") is not None

        # Pour mode 'caches', pas de restriction particulière
        if import_mode == "caches":
            return True

        return False

    @staticmethod
    def clean_html_content(content: str | None) -> str | None:
        """Nettoyer le contenu HTML (description, logs, etc.).

        Args:
            content: Contenu HTML brut.

        Returns:
            str | None: Contenu nettoyé ou None.
        """
        if not content:
            return None

        # Supprimer les balises HTML basiques
        # Note: Pour un nettoyage plus robuste, utiliser HTMLSanitizer
        cleaned = re.sub(r"<[^>]+>", "", content)
        cleaned = cleaned.strip()

        return cleaned if cleaned else None

    @staticmethod
    def extract_cache_metadata(raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extraire et normaliser les métadonnées d'une cache.

        Args:
            raw_data: Données brutes de la cache.

        Returns:
            dict: Métadonnées normalisées.
        """
        metadata = {}

        # Code GC (obligatoire)
        gc_code = DataNormalizer.normalize_gc_code(raw_data.get("gc_code"))
        if gc_code:
            metadata["GC"] = gc_code

        # Titre
        if raw_data.get("title"):
            metadata["title"] = str(raw_data["title"]).strip()

        # Description
        description = DataNormalizer.clean_html_content(raw_data.get("description"))
        if description:
            metadata["description_html"] = description

        # URL
        if raw_data.get("url"):
            metadata["url"] = str(raw_data["url"]).strip()

        # Coordonnées
        lat, lon = DataNormalizer.normalize_coordinates(
            raw_data.get("latitude"), raw_data.get("longitude")
        )
        if lat is not None and lon is not None:
            metadata["lat"] = lat
            metadata["lon"] = lon
            # GeoJSON pour index géographique
            metadata["loc"] = {"type": "Point", "coordinates": [lon, lat]}

        # Difficulté et terrain
        difficulty = DataNormalizer.normalize_difficulty_terrain(raw_data.get("difficulty"))
        if difficulty is not None:
            metadata["difficulty"] = difficulty

        terrain = DataNormalizer.normalize_difficulty_terrain(raw_data.get("terrain"))
        if terrain is not None:
            metadata["terrain"] = terrain

        # Date de placement
        placed_date = DataNormalizer.parse_datetime_iso8601(raw_data.get("placed_date"))
        if placed_date:
            metadata["placed_at"] = placed_date

        # Propriétaire
        if raw_data.get("owner"):
            metadata["owner"] = str(raw_data["owner"]).strip()

        # Favoris
        try:
            favorites = int(raw_data.get("favorites", 0))
            if favorites >= 0:
                metadata["favorites"] = favorites
        except (ValueError, TypeError):
            pass

        # Statut
        status = raw_data.get("status", "active").lower()
        if status in ["active", "disabled", "archived"]:
            metadata["status"] = status

        return metadata

    @staticmethod
    def extract_found_metadata(raw_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extraire les métadonnées de trouvaille.

        Args:
            raw_data: Données brutes incluant info de trouvaille.

        Returns:
            dict | None: Métadonnées de trouvaille ou None.
        """
        found_date = DataNormalizer.parse_datetime_iso8601(raw_data.get("found_date"))
        if not found_date:
            return None

        metadata = {
            "found_date": found_date,
        }

        # Notes de log
        notes = DataNormalizer.clean_html_content(raw_data.get("notes"))
        if notes:
            metadata["notes"] = notes

        return metadata
