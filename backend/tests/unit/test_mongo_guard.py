"""Tests for the integration-test guard that refuses non-local MongoDB hosts."""

import pytest

from tests.utils.mongo_guard import is_local_mongo_uri


class TestIsLocalMongoUri:
    @pytest.mark.parametrize(
        "uri",
        [
            "mongodb://localhost:27017",
            "mongodb://127.0.0.1:27017/?directConnection=true",
            "mongodb://mongo:27017",
            "mongodb://ci:ci@localhost:27017/geochallenge_ci_TEST",
            "mongodb://localhost:27017,127.0.0.1:27018",
            "mongodb://[::1]:27017",
        ],
    )
    def test_local_hosts_are_accepted(self, uri):
        assert is_local_mongo_uri(uri) is True

    @pytest.mark.parametrize(
        "uri",
        [
            "mongodb+srv://user:pass@cluster0.example.mongodb.net/?retryWrites=true",
            "mongodb://user:pass@db.example.com:27017",
            "mongodb://localhost:27017,db.example.com:27017",
            "mongodb://localhost.example.com:27017",
            "",
        ],
    )
    def test_remote_or_invalid_hosts_are_refused(self, uri):
        assert is_local_mongo_uri(uri) is False
