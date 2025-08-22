# backend/app/services/parsers/HTMLSanitizer.py

from selectolax.parser import HTMLParser, Node
from urllib.parse import urlparse

class HTMLSanitizer:
    def __init__(self, allowed_tags=None):
        """
        Initialize the HTML sanitizer with allowed tags.
        
        Args:
            allowed_tags (set): Set of allowed HTML tags. If None, uses a default safe set.
        """
        if allowed_tags is None:
            # Default safe tags (now includes 'a' for links)
            self.allowed_tags = {
                'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'div', 'span', 'blockquote', 'code', 'pre',
                'table', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot', 'a', 'img'
            }
        else:
            self.allowed_tags = set(allowed_tags)
    
    def _is_safe_href(self, href: str) -> bool:
        if not href:
            return False
        scheme = urlparse(href).scheme.lower()
        return scheme in ("http", "https", "mailto", "")

    def _escape(self, text: str) -> str:
        # mini-escape (selectolax ne fournit pas d’escape)
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

    # helper: concat des enfants
    def serialize_children(self, el) -> str:
        out = []
        child = el.child
        while child is not None:
            out.append(self._serialize_node(child))
            child = child.next
        return "".join(out)

    def _serialize_node(self, node) -> str:
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
        if not html:
            return ""
        tree = HTMLParser(html)
        # si on a un <body>, sérialiser ses enfants ; sinon root
        root = tree.body or tree.root
        self.remove_empty_nodes(root)
        result = self._serialize_node(root)

        return result

    def is_node_empty(self, node: Node) -> bool:
        """Détermine si un nœud est vide selon nos critères"""
        # Un nœud <br> n'est jamais considéré comme vide
        if node.tag in ['br', 'img']:
            return False
        
        # Si le nœud contient du texte non whitespace, il n'est pas vide
        if node.text(strip=True):
            return False
        
        # Vérifier les enfants
        has_significant_content = False
        for child in node.iter(include_text=False):
            # Si un enfant n'est pas un <br> et n'est pas vide
            if child.tag != 'br' and not self.is_node_empty(child):
                has_significant_content = True
                break
            # Si un enfant est un <br> avec du texte avant
            if child.tag == 'br' and child.prev and child.prev.text(strip=True):
                has_significant_content = True
                break
        
        return not has_significant_content

    def remove_empty_nodes(self, node: Node):
        """
        Parcourt récursivement l'arbre DOM et supprime les nœuds vides.
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

