# backend/app/services/gpx_import/cache_validator.py
# Validation métier des données de caches.

from __future__ import annotations

import re
from typing import Any


class CacheValidator:
    """Service de validation métier des caches.

    Description:
        Responsable de la validation des règles business
        pour les caches avant persistance en base.
    """

    def __init__(self, strict_mode: bool = False):
        """Initialiser le validateur.

        Args:
            strict_mode: Mode strict (rejeter les données incomplètes).
        """
        self.strict_mode = strict_mode

    def validate_cache_data(self, cache_data: dict[str, Any]) -> dict[str, Any]:
        """Valider et nettoyer les données d'une cache.

        Args:
            cache_data: Données de cache à valider.

        Returns:
            dict: Données de cache validées et nettoyées.

        Raises:
            ValueError: Si les données sont invalides.
        """
        validated = cache_data.copy()

        # Validation obligatoire: Code GC
        if not validated.get("GC"):
            raise ValueError("Missing required GC code")

        if not self._validate_gc_code(validated["GC"]):
            raise ValueError(f"Invalid GC code: {validated['GC']}")

        # Validation obligatoire: Titre
        if not validated.get("title"):
            if self.strict_mode:
                raise ValueError("Missing required title")
            validated["title"] = f"Cache {validated['GC']}"

        # Validation des coordonnées
        self._validate_coordinates(validated)

        # Validation difficulté/terrain
        self._validate_difficulty_terrain(validated)

        # Validation du propriétaire
        self._validate_owner(validated)

        # Validation des dates
        self._validate_dates(validated)

        # Validation des favoris
        self._validate_favorites(validated)

        # Validation du statut
        self._validate_status(validated)

        return validated

    def _validate_gc_code(self, gc_code: str) -> bool:
        """Valider un code GC.

        Args:
            gc_code: Code GC à valider.

        Returns:
            bool: True si valide.
        """
        if not isinstance(gc_code, str):
            return False

        # Format GCxxxxx (au moins 3 caractères après GC)
        pattern = r"^GC[A-Z0-9]{3,}$"
        return bool(re.match(pattern, gc_code.upper()))

    def _validate_coordinates(self, cache_data: dict[str, Any]) -> None:
        """Valider les coordonnées.

        Args:
            cache_data: Données de cache à valider.

        Raises:
            ValueError: Si les coordonnées sont invalides.
        """
        lat = cache_data.get("lat")
        lon = cache_data.get("lon")

        if lat is None or lon is None:
            if self.strict_mode:
                raise ValueError("Missing coordinates")
            return

        # Validation des types
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError("Coordinates must be numbers")

        # Validation des bornes
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat} (must be between -90 and 90)")

        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon} (must be between -180 and 180)")

        # Vérifier que ce ne sont pas des coordonnées nulles/invalides
        if lat == 0.0 and lon == 0.0:
            if self.strict_mode:
                raise ValueError("Invalid coordinates (0,0)")
            # En mode non-strict, supprimer les coordonnées invalides
            cache_data.pop("lat", None)
            cache_data.pop("lon", None)
            cache_data.pop("loc", None)

    def _validate_difficulty_terrain(self, cache_data: dict[str, Any]) -> None:
        """Valider difficulté et terrain.

        Args:
            cache_data: Données de cache à valider.

        Raises:
            ValueError: Si les valeurs sont invalides.
        """
        for field in ["difficulty", "terrain"]:
            value = cache_data.get(field)
            if value is None:
                continue

            if not isinstance(value, (int, float)):
                raise ValueError(f"{field} must be a number")

            if not (1.0 <= value <= 5.0):
                raise ValueError(f"{field} must be between 1.0 and 5.0, got {value}")

            # Arrondir à 0.5
            cache_data[field] = round(value * 2) / 2.0

    def _validate_owner(self, cache_data: dict[str, Any]) -> None:
        """Valider le propriétaire.

        Args:
            cache_data: Données de cache à valider.

        Raises:
            ValueError: Si le propriétaire est invalide.
        """
        owner = cache_data.get("owner")
        if owner is None:
            return

        if not isinstance(owner, str):
            cache_data["owner"] = str(owner)

        # Nettoyer le nom du propriétaire
        owner_clean = cache_data["owner"].strip()
        if not owner_clean:
            cache_data.pop("owner", None)
            return

        # Vérifier la longueur
        if len(owner_clean) > 100:
            raise ValueError("Owner name too long (max 100 characters)")

        cache_data["owner"] = owner_clean

    def _validate_dates(self, cache_data: dict[str, Any]) -> None:
        """Valider les dates.

        Args:
            cache_data: Données de cache à valider.

        Raises:
            ValueError: Si les dates sont invalides.
        """
        import datetime as dt

        # Valider placed_at
        placed_at = cache_data.get("placed_at")
        if placed_at is not None:
            if not isinstance(placed_at, dt.datetime):
                raise ValueError("placed_at must be a datetime object")

            # Vérifier que la date n'est pas dans le futur
            if placed_at > dt.datetime.utcnow():
                raise ValueError("placed_at cannot be in the future")

            # Vérifier que la date n'est pas trop ancienne (avant 2000)
            if placed_at.year < 2000:
                if self.strict_mode:
                    raise ValueError("placed_at seems too old (before 2000)")
                cache_data.pop("placed_at", None)

    def _validate_favorites(self, cache_data: dict[str, Any]) -> None:
        """Valider le nombre de favoris.

        Args:
            cache_data: Données de cache à valider.

        Raises:
            ValueError: Si le nombre est invalide.
        """
        favorites = cache_data.get("favorites")
        if favorites is None:
            return

        if not isinstance(favorites, int):
            try:
                favorites = int(favorites)
                cache_data["favorites"] = favorites
            except (ValueError, TypeError) as e:
                raise ValueError("favorites must be an integer") from e

        if favorites < 0:
            raise ValueError("favorites cannot be negative")

        # Limite raisonnable
        if favorites > 10000:
            if self.strict_mode:
                raise ValueError("favorites count seems too high")
            cache_data["favorites"] = 10000

    def _validate_status(self, cache_data: dict[str, Any]) -> None:
        """Valider le statut de la cache.

        Args:
            cache_data: Données de cache à valider.
        """
        status = cache_data.get("status")
        if status is None:
            cache_data["status"] = "active"  # Valeur par défaut
            return

        if not isinstance(status, str):
            cache_data["status"] = str(status).lower()
        else:
            cache_data["status"] = status.lower()

        # Valeurs autorisées
        valid_statuses = ["active", "disabled", "archived"]
        if cache_data["status"] not in valid_statuses:
            cache_data["status"] = "active"  # Valeur par défaut

    def validate_found_data(self, found_data: dict[str, Any]) -> dict[str, Any]:
        """Valider les données de trouvaille.

        Args:
            found_data: Données de trouvaille à valider.

        Returns:
            dict: Données de trouvaille validées.

        Raises:
            ValueError: Si les données sont invalides.
        """
        validated = found_data.copy()

        # Validation obligatoire: date de trouvaille
        if not validated.get("found_date"):
            raise ValueError("Missing required found_date")

        import datetime as dt

        if not isinstance(validated["found_date"], dt.datetime):
            raise ValueError("found_date must be a datetime object")

        # Vérifier que la date n'est pas dans le futur
        if validated["found_date"] > dt.datetime.utcnow():
            raise ValueError("found_date cannot be in the future")

        # Vérifier que la date n'est pas trop ancienne
        if validated["found_date"].year < 2000:
            if self.strict_mode:
                raise ValueError("found_date seems too old (before 2000)")

        # Valider les notes (optionnelles)
        if "notes" in validated:
            notes = validated["notes"]
            if notes is not None:
                if not isinstance(notes, str):
                    validated["notes"] = str(notes)

                # Limiter la longueur des notes
                if len(validated["notes"]) > 4000:
                    if self.strict_mode:
                        raise ValueError("Notes too long (max 4000 characters)")
                    validated["notes"] = validated["notes"][:4000]

        return validated

    def validate_import_consistency(
        self, cache_data: dict[str, Any], found_data: dict[str, Any] | None, import_mode: str
    ) -> None:
        """Valider la cohérence entre cache et trouvaille.

        Args:
            cache_data: Données de cache.
            found_data: Données de trouvaille (optionnel).
            import_mode: Mode d'import.

        Raises:
            ValueError: Si les données sont incohérentes.
        """
        # Vérifier que le mode d'import est respecté
        if import_mode == "found" and found_data is None:
            raise ValueError("found mode requires found_date")

        # Si on a une trouvaille, vérifier la cohérence des dates
        if found_data and cache_data.get("placed_at"):
            if found_data["found_date"] < cache_data["placed_at"]:
                raise ValueError("found_date cannot be before placed_at")

        # Vérifier que les codes GC correspondent (si trouvaille externe)
        if found_data and "GC" in found_data:
            if found_data["GC"] != cache_data.get("GC"):
                raise ValueError("GC code mismatch between cache and found data")
