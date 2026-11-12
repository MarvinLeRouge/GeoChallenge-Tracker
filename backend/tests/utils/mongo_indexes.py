"""Rebuild `create_index` arguments from a `list_indexes()` entry."""

# Index fields describing the index itself rather than a create_index option
_INDEX_META_FIELDS = {"key", "v", "ns", "textIndexVersion"}


def index_spec(idx: dict) -> tuple[list[tuple[str, object]], dict]:
    """Turn a `list_indexes()` entry into `create_index(keys, **options)` arguments.

    Every option is kept (unique, partialFilterExpression, collation, sparse...), so
    the copy enforces the same constraints as the source. A text index is listed as
    `{_fts: "text", _ftsx: 1}`; its real fields come from `weights`.

    Args:
        idx: One index document from `list_indexes()`.

    Returns:
        tuple: `(keys, options)` for `create_index`.
    """
    key = dict(idx.get("key", {}))
    if key.get("_fts") == "text":
        non_text = [(k, v) for k, v in key.items() if k not in ("_fts", "_ftsx")]
        keys = non_text + [(field, "text") for field in idx.get("weights", {})]
    else:
        keys = list(key.items())
    options = {k: v for k, v in idx.items() if k not in _INDEX_META_FIELDS}
    return keys, options
