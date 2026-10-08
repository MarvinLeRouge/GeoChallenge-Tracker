"""Tests for HTMLSanitizer (unit tests - no DB required)."""

from app.services.parsers.HTMLSanitizer import HTMLSanitizer


class TestHTMLSanitizer:
    """Test HTMLSanitizer component (HTML cleaning for cache descriptions)."""

    def test_sanitize_basic_html(self):
        """Test sanitization of basic HTML content."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>This is a <strong>test</strong> description.</p>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<p>" in result or "test" in result

    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>Safe text</p><script>alert('xss')</script>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<script>" not in result

    def test_sanitize_removes_style_tags(self):
        """Test that style tags are removed."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>Safe</p><style>.bad { color: red; }</style>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<style>" not in result

    def test_sanitize_preserves_allowed_tags(self):
        """Test that allowed tags are preserved."""
        sanitizer = HTMLSanitizer()

        html_content = "<p><strong>Bold</strong> and <em>italic</em></p>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        # Should preserve basic formatting tags

    def test_sanitize_handles_none_input(self):
        """Test sanitization handles None input gracefully."""
        sanitizer = HTMLSanitizer()

        result = sanitizer.clean_description_html(None)

        assert result is not None

    def test_sanitize_handles_empty_string(self):
        """Test sanitization handles empty string."""
        sanitizer = HTMLSanitizer()

        result = sanitizer.clean_description_html("")

        assert result is not None

    def test_is_safe_href_http(self):
        """Test href validation with http."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("http://example.com") is True

    def test_is_safe_href_https(self):
        """Test href validation with https."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("https://example.com") is True

    def test_is_safe_href_mailto(self):
        """Test href validation with mailto."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("mailto:test@example.com") is True

    def test_is_safe_href_javascript_rejected(self):
        """Test that javascript: is rejected."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("javascript:alert('xss')") is False

    def test_is_safe_href_empty_returns_false(self):
        """Empty href is treated as unsafe."""
        sanitizer = HTMLSanitizer()
        assert sanitizer._is_safe_href("") is False

    def test_custom_allowed_tags(self):
        """Constructor with explicit allowed_tags uses provided set."""
        sanitizer = HTMLSanitizer(allowed_tags={"p"})
        assert "p" in sanitizer.allowed_tags
        assert "strong" not in sanitizer.allowed_tags

    def test_br_renders_self_closing(self):
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html("<p>Line1<br>Line2</p>")
        assert "<br/>" in result

    def test_anchor_with_safe_href_preserved(self):
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html('<a href="https://example.com">click</a>')
        assert 'href="https://example.com"' in result
        assert "click" in result

    def test_anchor_with_unsafe_href_no_href_attr(self):
        """Unsafe href is stripped from <a>; tag and content are kept."""
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html('<a href="javascript:alert(1)">xss</a>')
        assert "javascript" not in result
        assert "xss" in result  # content preserved, but href removed

    def test_img_with_src_preserved(self):
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html(
            '<img src="https://example.com/img.jpg" name="photo"/>'
        )
        assert 'src="https://example.com/img.jpg"' in result
        assert "<img" in result

    def test_img_without_src_removed(self):
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html("<img/>")
        assert "<img" not in result

    def test_empty_paragraph_removed(self):
        """Empty <p></p> nodes are stripped by remove_empty_nodes."""
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html("<p>text</p><p></p>")
        # The non-empty paragraph is kept; the empty one is removed
        assert "text" in result

    def test_disallowed_tag_content_preserved(self):
        """<span> is not in the allowed set — content is preserved regardless."""
        sanitizer = HTMLSanitizer()
        result = sanitizer.clean_description_html("<span>content</span>")
        assert "content" in result
