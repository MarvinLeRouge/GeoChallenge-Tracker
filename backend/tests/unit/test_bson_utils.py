"""Tests for PyObjectId and bson_utils helpers (unit — pure)."""

from __future__ import annotations

import pytest
from bson import ObjectId
from pydantic import BaseModel

from app.core.bson_utils import MongoBaseModel, PyObjectId, dump_mongo, dump_mongo_json

# ---------------------------------------------------------------------------
# PyObjectId.__get_pydantic_json_schema__
# ---------------------------------------------------------------------------


class TestPyObjectIdJsonSchema:
    def test_json_schema_has_objectid_format(self):
        class M(BaseModel):
            my_id: PyObjectId

        schema = M.model_json_schema()
        props = schema.get("properties", {}).get("my_id", {})
        assert props.get("type") == "string"
        assert props.get("format") == "objectid"
        assert "pattern" in props


# ---------------------------------------------------------------------------
# PyObjectId._validate
# ---------------------------------------------------------------------------


class TestPyObjectIdValidate:
    def test_valid_objectid_passthrough(self):
        oid = ObjectId()
        result = PyObjectId._validate(oid, None)
        assert result is oid

    def test_valid_string_accepted(self):
        oid = ObjectId()
        result = PyObjectId._validate(str(oid), None)
        assert result == oid

    def test_invalid_value_raises_type_error(self):
        with pytest.raises(TypeError):
            PyObjectId._validate(12345, None)

    def test_invalid_string_raises_type_error(self):
        with pytest.raises(TypeError):
            PyObjectId._validate("not-a-valid-objectid", None)


# ---------------------------------------------------------------------------
# dump_mongo
# ---------------------------------------------------------------------------


class TestDumpMongo:
    def test_uses_alias_and_excludes_none(self):
        oid = ObjectId()
        model = MongoBaseModel(id=oid)
        result = dump_mongo(model)
        assert "_id" in result
        assert "id" not in result

    def test_include_none_when_disabled(self):
        model = MongoBaseModel()
        result = dump_mongo(model, exclude_none=False)
        assert "_id" in result


# ---------------------------------------------------------------------------
# dump_mongo_json
# ---------------------------------------------------------------------------


class TestDumpMongoJson:
    def test_returns_json_string(self):
        oid = ObjectId()
        model = MongoBaseModel(id=oid)
        result = dump_mongo_json(model)
        assert isinstance(result, str)
        assert str(oid) in result

    def test_exclude_none_by_default(self):
        model = MongoBaseModel()
        result = dump_mongo_json(model, exclude_none=True)
        assert result == "{}"
