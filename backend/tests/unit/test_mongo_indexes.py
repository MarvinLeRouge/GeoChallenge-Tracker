"""Tests for index_spec: a copied index keeps its options and its text fields."""

from tests.utils.mongo_indexes import index_spec


def test_partial_unique_index_keeps_its_options():
    idx = {
        "v": 2,
        "key": {"txt": 1},
        "name": "uniq_cache_attribute_txt",
        "unique": True,
        "partialFilterExpression": {"txt": {"$type": "string"}},
        "collation": {"locale": "en", "strength": 2},
    }
    keys, options = index_spec(idx)
    assert keys == [("txt", 1)]
    assert options == {
        "name": "uniq_cache_attribute_txt",
        "unique": True,
        "partialFilterExpression": {"txt": {"$type": "string"}},
        "collation": {"locale": "en", "strength": 2},
    }


def test_text_index_is_rebuilt_from_weights():
    idx = {
        "v": 2,
        "key": {"_fts": "text", "_ftsx": 1},
        "name": "text_title_desc",
        "weights": {"title": 1, "description_html": 1},
        "default_language": "english",
        "language_override": "language",
        "textIndexVersion": 3,
    }
    keys, options = index_spec(idx)
    assert keys == [("title", "text"), ("description_html", "text")]
    assert "textIndexVersion" not in options
    assert options["weights"] == {"title": 1, "description_html": 1}


def test_compound_text_index_keeps_its_prefix_fields():
    idx = {"key": {"owner": 1, "_fts": "text", "_ftsx": 1}, "name": "t", "weights": {"title": 1}}
    keys, _ = index_spec(idx)
    assert keys == [("owner", 1), ("title", "text")]
