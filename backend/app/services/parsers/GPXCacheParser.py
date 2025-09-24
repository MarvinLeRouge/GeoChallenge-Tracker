# backend/app/services/parsers/GPXCacheParser.py
# Parse un fichier GPX (ouvert depuis un chemin) pour extraire des géocaches structurées (métadonnées, attributs).

import html
from pathlib import Path
from typing import Any

from lxml import etree

from app.services.parsers.HTMLSanitizer import HTMLSanitizer


class GPXCacheParser:
    """Parseur GPX de géocaches.

    Description:
        Lit un fichier GPX (schémas `gpx`, `groundspeak`, `gsak`) et en extrait une
        liste de caches prêtes pour l’import : code GC, titre, coordonnées, type,
        taille, propriétaire, D/T, pays/état, description HTML (sanitisée), favoris,
        notes, dates (placement / found), attributs, etc.

    Attributes:
        gpx_file (Path): Chemin du fichier GPX.
        namespaces (dict): Préfixes d’espaces de noms XML utilisés pour les requêtes XPath.
        caches (list[dict]): Résultats accumulés après `parse()`.
        sanitizer (HTMLSanitizer): Sanitizeur HTML pour la description longue.
    """

    def __init__(self, gpx_file: Path):
        """Initialiser le parseur GPX.

        Description:
            Conserve le chemin vers le GPX, initialise les espaces de noms attendus
            et prépare les structures internes (liste `caches`, sanitizeur HTML).

        Args:
            gpx_file (Path): Chemin du fichier GPX à analyser.

        Returns:
            None
        """
        self.gpx_file = gpx_file
        self.namespaces = {
            "gpx": "http://www.topografix.com/GPX/1/0",
            "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
            "gsak": "http://www.gsak.net/xmlv1/6",
        }
        self.caches: list[dict] = []
        self.sanitizer = HTMLSanitizer()

    def test(self):
        """Lister tous les tags XML (debug).

        Description:
            Parse le fichier et itère sur tous les éléments pour imprimer
            leurs `tag` (utilitaire de mise au point).

        Args:
            None

        Returns:
            None
        """
        tree = etree.parse(str(self.gpx_file))
        for elem in tree.getroot().iter():
            print(elem.tag)

    def parse(self) -> list[dict]:
        """Analyser le GPX et remplir `self.caches`.

        Description:
            - Parcourt les waypoints `//gpx:wpt` et cherche le sous-élément `groundspeak:cache`.\n
            - Pour chaque cache finale (`_is_final_waypoint`), extrait les champs utiles
              (GC, titre, coords, type, taille, owner, D/T, pays/état, description HTML
              nettoyée, favoris GSAK, notes, dates, attributs via `_parse_attributes`).\n
            - Empile chaque dict dans `self.caches`.

        Args:
            None

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
                cache = {
                    "GC": self.find_text_deep(wpt, "gpx:name"),
                    "title": self.find_text_deep(wpt, "gpx:desc"),
                    "latitude": float(wpt.attrib["lat"]),
                    "longitude": float(wpt.attrib["lon"]),
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
                    "favorites": int(self.find_text_deep(wpt, "gsak:FavPoints") or 0),
                    "notes": self.find_text_deep(wpt, "gsak:GcNote"),
                    "placed_date": self.find_text_deep(wpt, "gpx:time"),
                    "found_date": self.find_text_deep(wpt, "gsak:UserFound"),
                    "attributes": self._parse_attributes(cache_elem),
                }
                self.caches.append(cache)

        return self.caches

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

    def _has_corrected_coordinates(self, wpt_elem) -> bool:
        """Indiquer si la cache a des coordonnées corrigées (placeholder).

        Description:
            Détecteur de coordonnées corrigées (ex. mystère résolue). Implémentation
            laissée volontairement minimale ; le retour peut être affiné selon besoin.

        Args:
            wpt_elem: Élément XML `<gpx:wpt>`.

        Returns:
            bool: True si coordonnées corrigées détectées, sinon False.
        """
        gsak_infos = wpt_elem.find("gsak:wptExtension", None)
        if gsak_infos is not None:
            print(gsak_infos)
        return wpt_elem.find("gsak:corrected", namespaces=self.namespaces) is not None

    def _has_found_log(self, cache_elem) -> bool:
        """Vérifier la présence d’un log « Found it ».

        Description:
            Cherche un nœud `groundspeak:log` dont le `type` (texte) vaut « Found it ».

        Args:
            cache_elem: Élément XML `<groundspeak:cache>`.

        Returns:
            bool: True si au moins un log « Found it » est présent, sinon False.
        """
        for log in cache_elem.xpath("groundspeak:logs/groundspeak:log", namespaces=self.namespaces):
            log_type = self._text(log.find("groundspeak:type", namespaces=self.namespaces))
            if log_type.lower() == "found it":
                return True
        return False

    def _was_found(self, wpt_elem) -> bool:
        """Déterminer si la cache a un indicateur GSAK « UserFound ».

        Description:
            Vérifie la présence d’un champ `gsak:UserFound`/`gsak:userfound` indiquant
            que la cache a été loguée trouvée par l’utilisateur côté GSAK.

        Args:
            wpt_elem: Élément XML `<gpx:wpt>`.

        Returns:
            bool: True si indicateur présent, sinon False.
        """
        return wpt_elem.find("gsak:userfound", namespaces=self.namespaces) is not None

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

    def _text(self, element, default: str = "") -> str:
        """Lire le texte d’un élément (strip), avec défaut.

        Args:
            element: Élément XML ou None.
            default (str): Valeur par défaut si texte absent.

        Returns:
            str: Contenu textuel nettoyé.
        """
        return element.text.strip() if element is not None and element.text else default

    def _html(self, element, default: str = "") -> str:
        """Lire du HTML (texte) et le déséchapper.

        Description:
            Retourne `html.unescape(element.text.strip())` si présent.

        Args:
            element: Élément XML ou None.
            default (str): Valeur par défaut si vide.

        Returns:
            str: HTML déséchappé (ou chaîne vide).
        """
        return html.unescape(element.text.strip()) if element is not None and element.text else ""

    def get_caches(self) -> list[dict]:
        """Récupérer la liste des caches déjà extraites.

        Args:
            None

        Returns:
            list[dict]: Valeur actuelle de `self.caches`.
        """
        return self.caches

    def find_text_deep(self, element, tag: str) -> str:
        """Trouver du texte via XPath relatif (`.//{tag}`).

        Description:
            Exécute `element.xpath(f".//{tag}", namespaces=self.namespaces)` et retourne
            le premier texte trouvé (strip) ou une chaîne vide.

        Args:
            element: Élément de départ pour la recherche.
            tag (str): Tag XPath qualifié par préfixe (ex. `gpx:name`).

        Returns:
            str: Texte trouvé, sinon chaîne vide.
        """
        found = element.xpath(f".//{tag}", namespaces=self.namespaces)
        return found[0].text.strip() if found and len(found) and found[0].text else ""
