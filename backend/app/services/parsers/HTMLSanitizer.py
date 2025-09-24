# backend/app/services/parsers/HTMLSanitizer.py
# Sanitizeur HTML : garde un sous-ensemble de balises sûres, échappe le texte et élague le vide.

from urllib.parse import urlparse

from selectolax.parser import HTMLParser


class HTMLSanitizer:
    """Sanitizeur HTML basé sur selectolax.

    Description:
        Sérialise un fragment HTML en conservant uniquement des balises sûres
        (p, br, strong, em, titres, listes, table, a, img, etc.).\n
        - Les liens <a> ne sont gardés que pour des schémas sûrs (http/https/mailto).\n
        - Les <script>/<style> sont supprimés.\n
        - Les balises non autorisées sont « déroulées » (contenu conservé, tag supprimé).\n
        - Les nœuds vides sont retirés.

    Attributes:
        allowed_tags (set[str]): Ensemble de balises autorisées.
    """

    def __init__(self, allowed_tags=None):
        """Initialiser le sanitizeur.

        Args:
            allowed_tags (set | None): Ensemble de balises autorisées ; par défaut,
                utilise un set « sûr » incluant `a` et `img`.

        Returns:
            None
        """
        if allowed_tags is None:
            # Default safe tags (now includes 'a' for links)
            self.allowed_tags = {
                "p",
                "br",
                "strong",
                "em",
                "u",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "ul",
                "ol",
                "li",
                "div",
                "span",
                "blockquote",
                "code",
                "pre",
                "table",
                "tr",
                "td",
                "th",
                "thead",
                "tbody",
                "tfoot",
                "a",
                "img",
            }
        else:
            self.allowed_tags = set(allowed_tags)

    def _is_safe_href(self, href: str) -> bool:
        """Vérifier qu’un href est « sûr ».

        Description:
            Autorise les schémas `http`, `https`, `mailto` (ou vide). Refuse les autres.

        Args:
            href (str): Valeur de l’attribut href.

        Returns:
            bool: True si le lien est autorisé, sinon False.
        """
        if not href:
            return False
        scheme = urlparse(href).scheme.lower()
        return scheme in ("http", "https", "mailto", "")

    def _escape(self, text: str) -> str:
        """Échapper minimalement le texte (HTML).

        Description:
            Remplace `&`, `<`, `>` par les entités équivalentes. Utile pour les nœuds texte.

        Args:
            text (str): Chaîne source.

        Returns:
            str: Chaîne échappée.
        """
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # helper: concat des enfants
    def serialize_children(self, el) -> str:
        """Sérialiser les enfants d’un nœud.

        Description:
            Concatène la sérialisation de chaque enfant en respectant l’ordre.

        Args:
            el: Nœud parent (selectolax Node).

        Returns:
            str: HTML sérialisé des enfants.
        """
        out = []
        child = el.child
        while child is not None:
            out.append(self._serialize_node(child))
            child = child.next
        return "".join(out)

    def _serialize_node(self, node) -> str:
        """Sérialiser récursivement un nœud.

        Description:
            - Texte → échappé.\n
            - `<script>/<style>` → supprimés.\n
            - Balise autorisée → rendue (avec gestion spécifique pour `<a>` et `<img>`).\n
            - Autre balise → contenu déroulé (tag supprimé).

        Args:
            node: Nœud selectolax.

        Returns:
            str: HTML sérialisé.
        """
        # Text node
        if node.tag == "-text":
            return self._escape(node.text() or "")

        tag = (node.tag or "").lower()

        # drop <script>/<style> entièrement
        if tag in ("script", "style"):
            return ""

        # balise autorisée
        if tag in self.allowed_tags:
            if tag == "br":
                return "<br/>"
            if tag == "a":
                href = node.attributes.get("href")
                attrs = f' href="{href}"' if href and self._is_safe_href(href) else ""
                return f"<a{attrs}>{self.serialize_children(node)}</a>"
            if tag == "img":
                src = node.attributes.get("src", None)
                if src is None:
                    return ""
                name = node.attributes.get("name", "")
                attrs = f' src="{src}" name="{name}"'
                return f"<img{attrs} />"
            # autres tags autorisés sans attributs
            return f"<{tag}>{self.serialize_children(node)}</{tag}>"

        # balise non autorisée (ex: span, font, center, etc.) → on déroule le contenu
        return self.serialize_children(node)

    def clean_description_html(self, html: str) -> str:
        """Nettoyer un fragment HTML.

        Description:
            Parse le HTML, récupère le `<body>` s’il existe, supprime les nœuds
            vides via `remove_empty_nodes`, puis sérialise le résultat.

        Args:
            html (str): Fragment HTML d’entrée.

        Returns:
            str: HTML nettoyé et sûr (sous-ensemble autorisé).
        """
        if not html:
            return ""
        tree = HTMLParser(html)
        # si on a un <body>, sérialiser ses enfants ; sinon root
        root = tree.body or tree.root
        self.remove_empty_nodes(root)
        result = self._serialize_node(root)

        return result

    def is_node_empty(self, node) -> bool:
        """Tester si un nœud est « vide » selon nos règles.

        Description:
            - `<br>` et `<img>` ne sont jamais considérés vides.\n
            - Toute présence de texte non-blanc rend le nœud non vide.\n
            - Sinon, inspecte les enfants pour décider.

        Args:
            node: Nœud selectolax.

        Returns:
            bool: True si le nœud est vide, sinon False.
        """
        # Un nœud <br> n'est jamais considéré comme vide
        if node.tag in ["br", "img"]:
            return False

        # Si le nœud contient du texte non whitespace, il n'est pas vide
        if node.text(strip=True):
            return False

        # Vérifier les enfants
        has_significant_content = False
        for child in node.iter(include_text=False):
            # Si un enfant n'est pas un <br> et n'est pas vide
            if child.tag != "br" and not self.is_node_empty(child):
                has_significant_content = True
                break
            # Si un enfant est un <br> avec du texte avant
            if child.tag == "br" and child.prev and child.prev.text(strip=True):
                has_significant_content = True
                break

        return not has_significant_content

    def remove_empty_nodes(self, node) -> None:
        """Supprimer récursivement les nœuds vides d’un sous-arbre.

        Description:
            Parcours en profondeur (post-ordre) pour identifier et éliminer les
            nœuds vides selon `is_node_empty`.

        Args:
            node: Racine du sous-arbre à nettoyer.

        Returns:
            None
        """
        # Parcours en profondeur d'abord (post-order)
        for child in node.iter(include_text=False):
            self.remove_empty_nodes(child)

        # Collecter les enfants à supprimer
        children_to_remove = []
        for child in node.iter(include_text=False):
            if self.is_node_empty(child):
                children_to_remove.append(child)

        # Supprimer les nœuds vides
        for child in children_to_remove:
            child.decompose()
