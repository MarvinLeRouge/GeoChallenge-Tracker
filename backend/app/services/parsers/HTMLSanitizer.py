# backend/app/services/parsers/HTMLSanitizer.py
# HTML sanitizer: retains a safe tag subset, escapes text, and removes empty nodes.

from urllib.parse import urlparse

from selectolax.parser import HTMLParser


class HTMLSanitizer:
    """selectolax-based HTML sanitizer.

    Description:
        Serializes an HTML fragment keeping only a safe subset of tags
        (p, br, strong, em, headings, lists, table, a, img, etc.).\n
        - <a> links are kept only for safe schemes (http/https/mailto).\n
        - <script>/<style> elements are dropped entirely.\n
        - Disallowed tags are "unwrapped" (content kept, tag removed).\n
        - Empty nodes are removed.

    Attributes:
        allowed_tags (set[str]): Set of allowed HTML tags.
    """

    def __init__(self, allowed_tags=None):
        """Initialize the sanitizer.

        Args:
            allowed_tags (set | None): Set of allowed tags; defaults to a safe set
                that includes `a` and `img`.

        Returns:
            None
        """
        if allowed_tags is None:
            # Default safe tag set (includes 'a' for links)
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
        """Check whether an href is safe.

        Description:
            Allows `http`, `https`, `mailto` schemes (or empty). Rejects all others.

        Args:
            href (str): Value of the href attribute.

        Returns:
            bool: True if the link is allowed, otherwise False.
        """
        if not href:
            return False
        scheme = urlparse(href).scheme.lower()
        return scheme in ("http", "https", "mailto", "")

    def _escape(self, text: str) -> str:
        """Minimally escape HTML text.

        Description:
            Replaces `&`, `<`, `>` with their HTML entity equivalents. Useful for text nodes.

        Args:
            text (str): Source string.

        Returns:
            str: Escaped string.
        """
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # helper: concatenate children
    def serialize_children(self, el) -> str:
        """Serialize the children of a node.

        Description:
            Concatenates the serialization of each child in document order.

        Args:
            el: Parent node (selectolax Node).

        Returns:
            str: Serialized HTML of the children.
        """
        out = []
        child = el.child
        while child is not None:
            out.append(self._serialize_node(child))
            child = child.next
        return "".join(out)

    def _serialize_node(self, node) -> str:
        """Recursively serialize a node.

        Description:
            - Text node → escaped.\n
            - `<script>/<style>` → dropped entirely.\n
            - Allowed tag → rendered (with specific handling for `<a>` and `<img>`).\n
            - Other tag → content unwrapped (tag removed).

        Args:
            node: selectolax node.

        Returns:
            str: Serialized HTML.
        """
        # Text node
        if node.tag == "-text":
            return self._escape(node.text() or "")

        tag = (node.tag or "").lower()

        # drop <script>/<style> entirely
        if tag in ("script", "style"):
            return ""

        # allowed tag
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
            # other allowed tags rendered without attributes
            return f"<{tag}>{self.serialize_children(node)}</{tag}>"

        # disallowed tag (e.g. span, font, center, etc.) → unwrap content
        return self.serialize_children(node)

    def clean_description_html(self, html: str) -> str:
        """Clean an HTML fragment.

        Description:
            Parses the HTML, retrieves the `<body>` if present, removes empty nodes
            via `remove_empty_nodes`, then serializes the result.

        Args:
            html (str): Input HTML fragment.

        Returns:
            str: Cleaned, safe HTML (allowed subset only).
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
        """Test whether a node is "empty" according to our rules.

        Description:
            - `<br>` and `<img>` are never considered empty.\n
            - Any non-whitespace text makes the node non-empty.\n
            - Otherwise, inspects children to decide.

        Args:
            node: selectolax node.

        Returns:
            bool: True if the node is empty, otherwise False.
        """
        # A <br> or <img> node is never considered empty
        if node.tag in ["br", "img"]:
            return False

        # If the node contains non-whitespace text, it is not empty
        if node.text(strip=True):
            return False

        # Check children
        has_significant_content = False
        for child in node.iter(include_text=False):
            # If a child is not a <br> and is not empty
            if child.tag != "br" and not self.is_node_empty(child):
                has_significant_content = True
                break
            # If a child is a <br> with preceding text
            if child.tag == "br" and child.prev and child.prev.text(strip=True):
                has_significant_content = True
                break

        return not has_significant_content

    def remove_empty_nodes(self, node) -> None:
        """Recursively remove empty nodes from a subtree.

        Description:
            Depth-first (post-order) traversal to identify and eliminate
            empty nodes as determined by `is_node_empty`.

        Args:
            node: Root of the subtree to clean.

        Returns:
            None
        """
        # Depth-first traversal (post-order)
        for child in node.iter(include_text=False):
            self.remove_empty_nodes(child)

        # Collect children to remove
        children_to_remove = []
        for child in node.iter(include_text=False):
            if self.is_node_empty(child):
                children_to_remove.append(child)

        # Remove empty nodes
        for child in children_to_remove:
            child.decompose()
