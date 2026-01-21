# backend/app/services/parsers/MultiFormatGPXParser.py
# Parse un fichier GPX de plusieurs formats (cgeo, pocket query, etc.) pour extraire des géocaches structurées.

from pathlib import Path
from typing import Any, Optional

from lxml import etree


class MultiFormatGPXParser:
    """Parseur GPX multi-format de géocaches.

    Description:
        Lit un fichier GPX de différents formats (cgeo, pocket query) et en extrait une
        liste de caches prêtes pour l’import : code GC, titre, coordonnées, type,
        taille, propriétaire, D/T, pays/état, description HTML (sanitisée), favoris,
        notes, dates (placement / found), attributs, etc.

    Attributes:
        gpx_file (Path): Chemin du fichier GPX.
        format_type (str): Format spécifié ou détecté ('cgeo', 'pocket_query', etc.).
        namespaces (dict): Préfixes d’espaces de noms XML utilisés pour les requêtes XPath.
        caches (list[dict]): Résultats accumulés après `parse`.
        sanitizer (HTMLSanitizer): Sanitizeur HTML pour la description longue.
    """

    def __init__(self, gpx_file: Path, format_type: str = "auto"):
        """Initialiser le parseur GPX multi-format.

        Args:
            gpx_file (Path): Chemin du fichier GPX à analyser.
            format_type (str): Type de format à utiliser - 'auto' pour détection automatique,
                               'cgeo', 'pocket_query' pour forcer un format spécifique.

        Returns:
            None
        """
        self.gpx_file = gpx_file

        if format_type == "auto":
            self.format_type = self._detect_format()
        else:
            # Valider que le format demandé est supporté
            if format_type in ["cgeo", "pocket_query"]:
                self.format_type = format_type
            else:
                print(f"Format {format_type} non supporté, utilisation de la détection automatique")
                self.format_type = self._detect_format()

        # Définir les namespaces en fonction du format détecté ou spécifié
        self.namespaces = self._get_namespaces_for_format(self.format_type)

        self.caches: list[dict] = []

        # Importer HTMLSanitizer localement pour éviter les dépendances circulaires
        from app.services.parsers.HTMLSanitizer import HTMLSanitizer

        self.sanitizer = HTMLSanitizer()

    def _detect_format(self) -> str:
        """Détecter le format du GPX en lisant les métadonnées racines.

        Description:
            Détecte le format en fonction du créateur ou des URLs de schéma présentes
            dans l'élément racine.

        Returns:
            str: Format détecté ('cgeo' ou 'pocket_query')
        """
        try:
            tree = etree.parse(str(self.gpx_file))
            root = tree.getroot()

            # Vérifier le créateur du fichier
            creator = root.get("creator", "").lower()
            if "cgeo" in creator or "c:geo" in creator:
                return "cgeo"

            # Vérifier les URL de schéma
            schema_location = root.get(
                "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", ""
            ).lower()
            if "cgeo" in schema_location:
                return "cgeo"

            # Vérifier si c'est une Pocket Query
            if "pocket query" in schema_location or "pocket query" in creator:
                return "pocket_query"

            # Vérifier le namespace groundspeak s'il est présent dans l'élément racine
            for _prefix, uri in root.nsmap.items():
                if "groundspeak.com/cache" in uri:
                    # Vérifier la version spécifique du schema
                    if "1/0/1" in uri:
                        return "cgeo"
                    elif "1/0" in uri:
                        return "pocket_query"

            # Dernier recours: chercher dans le contenu texte
            root_text = etree.tostring(root, encoding="unicode", method="xml").lower()
            if "c:geo" in root_text:
                return "cgeo"
            elif "pocket query" in root_text:
                return "pocket_query"

        except Exception as e:
            print(f"Erreur lors de la détection de format: {e}")

        # Par défaut, supposer cgeo
        return "cgeo"

    def _get_namespaces_for_format(self, format_type: str) -> dict[str, str]:
        """Retourner les namespaces appropriés pour un format donné."""
        if format_type == "cgeo":
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
                "gsak": "http://www.gsak.net/xmlv1/6",
            }
        elif format_type == "pocket_query":
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0",  # 1/0 au lieu de 1/0/1
            }
        else:
            # Format inconnu, utiliser le format cgeo par défaut
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
                "gsak": "http://www.gsak.net/xmlv1/6",
            }

    def parse(self) -> list[dict]:
        """Analyser le GPX en fonction du format détecté ou spécifié et remplir `self.caches`.

        Description:
            - Parcourt les waypoints `//gpx:wpt` et cherche le sous-élément `groundspeak:cache`.\n
            - Pour chaque cache finale (`_is_final_waypoint`), extrait les champs utiles
              (GC, titre, coords, type, taille, owner, D/T, pays/état, description HTML
              nettoyée, favoris GSAK, notes, dates, attributs via `_parse_attributes`).\n
            - Empile chaque dict dans `self.caches`.

        Returns:
            list[dict]: Liste de caches structurées prêtes à l’import.
        """
        tree = etree.parse(str(self.gpx_file))
        nodes: Any = tree.xpath("//gpx:wpt", namespaces=self.namespaces)
        if not isinstance(nodes, list):
            raise ValueError("XPath did not return nodes")

        for wpt in nodes:
            cache_elem = wpt.find("groundspeak:cache", namespaces=self.namespaces)
            if cache_elem is None:
                continue

            is_final = self._is_final_waypoint(cache_elem)
            if is_final:
                # Extraire les données en fonction du format
                cache = self._extract_cache_data(wpt, cache_elem)
                if cache["GC"] == "GCAW0J4":
                    print("cache", cache)
                self.caches.append(cache)

        return self.caches

    def _extract_cache_data(self, wpt, cache_elem) -> dict:
        """Extraire les données de cache selon le format détecté."""
        # Commencer avec les champs de base qui sont communs
        cache = {
            "GC": self.find_text_deep(wpt, "gpx:name"),
            "title": self.find_text_deep(wpt, "gpx:desc"),
            "latitude": float(wpt.attrib["lat"]) if "lat" in wpt.attrib else None,
            "longitude": float(wpt.attrib["lon"]) if "lon" in wpt.attrib else None,
            "cache_type": self.find_text_deep(wpt, "groundspeak:type"),
            "cache_size": self.find_text_deep(wpt, "groundspeak:container"),
            "owner": self.find_text_deep(wpt, "groundspeak:owner"),
            "difficulty": self.find_text_deep(wpt, "groundspeak:difficulty"),
            "terrain": self.find_text_deep(wpt, "groundspeak:terrain"),
            "country": self.find_text_deep(wpt, "groundspeak:country"),
            "state": self.find_text_deep(wpt, "groundspeak:state"),
            "description_html": self.sanitizer.clean_description_html(
                self.find_text_deep(wpt, "groundspeak:long_description")
            ),
            "placed_date": self.find_text_deep(wpt, "gpx:time"),
            "attributes": self._parse_attributes(cache_elem),
        }

        # Ajouter les champs spécifiques selon le format
        if self.format_type == "cgeo":
            # Champs spécifiques au format cgeo (avec GSAK)
            cache["favorites"] = int(self.find_text_deep(wpt, "gsak:FavPoints") or 0)
            cache["notes"] = self.find_text_deep(wpt, "gsak:GcNote")
            cache["found_date"] = self.find_text_deep(wpt, "gsak:UserFound")
        elif self.format_type == "pocket_query":
            # Champs spécifiques au format pocket query
            # Pour le moment, on initialise avec des valeurs par défaut
            # On peut améliorer cela en cherchant d'autres champs spécifiques
            cache["favorites"] = 0  # Les pocket queries n'ont pas de FavPoints GSAK
            cache["notes"] = None

            # Vérifier si des logs sont disponibles dans le format pocket query
            found_date = self._extract_found_date_from_logs(cache_elem)

            # Pour les caches de type événementiel, si aucune date de trouvaille n'est trouvée,
            # utiliser la date de placement (time) comme date de trouvaille
            raw_cache_type = cache.get("cache_type", "")

            # On s'assure que c'est une string avant le .lower()
            if isinstance(raw_cache_type, str):
                cache_type = raw_cache_type.lower()
            else:
                # Si c'est un autre type (float, list, etc.), on le convertit en str
                cache_type = str(raw_cache_type).lower()

            if not found_date and ("event" in cache_type):
                # Prendre la date de placement comme date de trouvaille pour les événements
                # Essayer d'abord le champ direct <time> puis gpx:time
                event_time = self.find_text_deep(wpt, "time") or self.find_text_deep(
                    wpt, "gpx:time"
                )
                if event_time:
                    found_date = event_time
                    if not found_date.endswith("Z"):
                        found_date += "Z"

            cache["found_date"] = found_date

        return cache

    def _extract_found_date_from_logs(self, cache_elem) -> Optional[str]:
        """Tenter d'extraire la date de trouvaille à partir des logs dans le format pocket query."""
        # Récupérer tous les logs de la cache
        logs = cache_elem.xpath("groundspeak:logs/groundspeak:log", namespaces=self.namespaces)

        # Si aucun log, retourner None
        if not logs:
            return None

        # Si un seul log et que ce format est "pocket query", utiliser sa date comme found_date
        if self.format_type == "pocket_query" and len(logs) == 1:
            date = self.find_text_deep(logs[0], "groundspeak:date")
            if date:
                # S'assurer que la date se termine par Z si nécessaire
                if not date.endswith("Z"):
                    date += "Z"
                return date

        # Sinon, continuer avec la logique originale (cherche les logs de type "found")
        for log in logs:
            log_type = self.find_text_deep(log, "groundspeak:type")
            if log_type and "found" in log_type.lower():
                date = self.find_text_deep(log, "groundspeak:date")
                if date:
                    return date
        return None

    def _parse_attributes(self, cache_elem) -> list[dict]:
        """Extraire la liste des attributs depuis `<groundspeak:attributes>`.

        Description:
            Parcourt les nœuds `groundspeak:attribute` et retourne des objets
            `{id: int, is_positive: bool, name: str}`.

        Args:
            cache_elem: Élément XML `<groundspeak:cache>` parent.

        Returns:
            list[dict]: Attributs normalisés (id / inc / libellé).
        """
        attrs = []
        for attr in cache_elem.xpath(
            "groundspeak:attributes/groundspeak:attribute", namespaces=self.namespaces
        ):
            attrs.append(
                {
                    "id": int(attr.get("id")),
                    "is_positive": attr.get("inc") == "1",
                    "name": attr.text.strip() if attr.text else "",
                }
            )

        return attrs

    def _is_final_waypoint(self, cache_elem) -> bool:
        """Filtrer les waypoints finaux (placeholder).

        Description:
            Point d’extension pour n’extraire que certains waypoints (ex. finals).
            Implémentation actuelle retourne systématiquement True.

        Args:
            cache_elem: Élément XML `<groundspeak:cache>`.

        Returns:
            bool: True si le waypoint doit être conservé.
        """
        return True

    def find_text_deep(self, element, tag: str) -> str:
        """Trouver du texte via XPath relatif (`.//{tag}`).

        Args:
            element: Élément de départ pour la recherche.
            tag (str): Tag XPath qualifié par préfixe (ex. `gpx:name`).

        Returns:
            str: Texte trouvé, sinon chaîne vide.
        """
        found = element.xpath(f".//{tag}", namespaces=self.namespaces)
        return found[0].text.strip() if found and len(found) and found[0].text else ""

    def get_caches(self) -> list[dict]:
        """Récupérer la liste des caches déjà extraites.

        Returns:
            list[dict]: Valeur actuelle de `self.caches`.
        """
        return self.caches
