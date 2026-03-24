"""Tests for db/mongodb.py, elevation_retrieval.py, and geocoding_nominatim.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# db/mongodb.py
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_creates_client_on_first_call(self):
        import app.db.mongodb as mod

        old_client = mod._client
        mod._client = None

        mock_client = MagicMock()
        with patch("app.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
            result = mod.get_client()

        assert result is mock_client
        mod._client = old_client

    def test_reuses_existing_client(self):
        import app.db.mongodb as mod

        sentinel = MagicMock()
        old = mod._client
        mod._client = sentinel

        result = mod.get_client()
        assert result is sentinel
        mod._client = old


class TestGetDb:
    def test_creates_db_from_client(self):
        import app.db.mongodb as mod

        old_db = mod._db
        mod._db = None

        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("app.db.mongodb.get_client", return_value=mock_client):
            result = mod.get_db()

        assert result is mock_db
        mod._db = old_db

    def test_reuses_existing_db(self):
        import app.db.mongodb as mod

        sentinel = MagicMock()
        old = mod._db
        mod._db = sentinel

        result = mod.get_db()
        assert result is sentinel
        mod._db = old


class TestGetColumn:
    @pytest.mark.asyncio
    async def test_returns_values_from_collection(self):
        mock_db = MagicMock()

        # Create an async iterable that yields docs
        async def aiter_docs():
            for doc in [{"name": "alice"}, {"name": "bob"}]:
                yield doc

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = MagicMock(return_value=aiter_docs())
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        mock_db.__getitem__.return_value.find = MagicMock(return_value=mock_cursor)

        with patch("app.db.mongodb.get_db", return_value=mock_db):
            from app.db.mongodb import get_column

            result = await get_column("users", "name")

        assert result == ["alice", "bob"]

    @pytest.mark.asyncio
    async def test_applies_limit_when_positive(self):
        mock_db = MagicMock()

        async def aiter_docs():
            for doc in [{"name": "alice"}]:
                yield doc

        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = MagicMock(return_value=aiter_docs())
        mock_coll = MagicMock()
        mock_coll.find = MagicMock(return_value=mock_cursor)
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        with patch("app.db.mongodb.get_db", return_value=mock_db):
            from app.db.mongodb import get_column

            await get_column("users", "name", limit=5)

        mock_cursor.limit.assert_called_once_with(5)


class TestGetCollection:
    @pytest.mark.asyncio
    async def test_returns_collection_from_db(self):
        mock_coll = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        with patch("app.db.mongodb.get_db", return_value=mock_db):
            from app.db.mongodb import get_collection

            result = await get_collection("users")

        assert result is mock_coll


class TestGetDistinct:
    @pytest.mark.asyncio
    async def test_returns_distinct_values(self):
        mock_db = MagicMock()
        mock_coll = AsyncMock()
        mock_coll.distinct = AsyncMock(return_value=["a", "b"])
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        with patch("app.db.mongodb.get_db", return_value=mock_db):
            from app.db.mongodb import get_distinct

            result = await get_distinct("coll", "field")

        assert result == ["a", "b"]


class TestCloseMongodbConnection:
    @pytest.mark.asyncio
    async def test_closes_client_and_resets_globals(self):
        import app.db.mongodb as mod

        mock_client = MagicMock()
        old_client = mod._client
        old_db = mod._db
        mod._client = mock_client
        mod._db = MagicMock()

        from app.db.mongodb import close_mongodb_connection

        await close_mongodb_connection()

        mock_client.close.assert_called_once()
        assert mod._client is None
        assert mod._db is None

        mod._client = old_client
        mod._db = old_db

    @pytest.mark.asyncio
    async def test_does_nothing_when_no_client(self):
        import app.db.mongodb as mod

        old_client = mod._client
        mod._client = None

        from app.db.mongodb import close_mongodb_connection

        # Should not raise
        await close_mongodb_connection()

        mod._client = old_client


# ---------------------------------------------------------------------------
# elevation_retrieval.py
# ---------------------------------------------------------------------------


class TestElevationFetch:
    @pytest.mark.asyncio
    async def test_returns_nones_when_no_provider(self):
        with patch("app.services.elevation_retrieval.DEFAULT_PROVIDER", ""):
            from app.services.elevation_retrieval import fetch

            result = await fetch([(48.0, 2.0), (49.0, 3.0)])

        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_returns_nones_for_unknown_provider(self):
        with patch("app.services.elevation_retrieval.DEFAULT_PROVIDER", "unknown_provider"):
            from app.services.elevation_retrieval import fetch

            result = await fetch([(48.0, 2.0)])

        assert result == [None]

    @pytest.mark.asyncio
    async def test_delegates_to_provider_function(self):
        mock_provider = AsyncMock(return_value=[150, 200])

        with (
            patch("app.services.elevation_retrieval.DEFAULT_PROVIDER", "opentopo"),
            patch("app.services.elevation_retrieval._PROVIDERS", {"opentopo": mock_provider}),
        ):
            from app.services.elevation_retrieval import fetch

            result = await fetch([(48.0, 2.0), (49.0, 3.0)])

        assert result == [150, 200]
        mock_provider.assert_called_once()


# ---------------------------------------------------------------------------
# geocoding_nominatim.py
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_returns_none_when_no_country(self):
        from app.services.providers.geocoding_nominatim import _parse_response

        result = _parse_response({"address": {}})
        assert result is None

    def test_returns_country_and_state(self):
        from app.services.providers.geocoding_nominatim import _parse_response

        data = {"address": {"country": "France", "state": "Île-de-France"}}
        result = _parse_response(data)
        assert result == ("France", "Île-de-France")

    def test_falls_back_to_region_when_no_state(self):
        from app.services.providers.geocoding_nominatim import _parse_response

        data = {"address": {"country": "Spain", "region": "Catalonia"}}
        result = _parse_response(data)
        assert result == ("Spain", "Catalonia")

    def test_falls_back_to_county(self):
        from app.services.providers.geocoding_nominatim import _parse_response

        data = {"address": {"country": "USA", "county": "Los Angeles"}}
        result = _parse_response(data)
        assert result == ("USA", "Los Angeles")

    def test_empty_country_returns_none(self):
        from app.services.providers.geocoding_nominatim import _parse_response

        data = {"address": {"country": "   "}}  # whitespace only
        result = _parse_response(data)
        assert result is None


class TestFetchOne:
    @pytest.mark.asyncio
    async def test_returns_parsed_result_on_200(self):
        from app.services.providers.geocoding_nominatim import fetch_one

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"address": {"country": "France", "state": "Paris"}}
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result, status = await fetch_one(48.85, 2.35, mock_client)
        assert result == ("France", "Paris")
        assert status == 200

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        from app.services.providers.geocoding_nominatim import fetch_one

        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result, status = await fetch_one(48.85, 2.35, mock_client)
        assert result is None
        assert status == 429

    @pytest.mark.asyncio
    async def test_returns_none_and_zero_on_exception(self):
        from app.services.providers.geocoding_nominatim import fetch_one

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

        result, status = await fetch_one(48.85, 2.35, mock_client)
        assert result is None
        assert status == 0


class TestFetchBatch:
    @pytest.mark.asyncio
    async def test_empty_points_returns_empty(self):
        from app.services.providers.geocoding_nominatim import fetch_batch

        results, stats = await fetch_batch([])
        assert results == []
        assert stats == {}

    @pytest.mark.asyncio
    async def test_single_point_no_delay(self):
        from app.services.providers.geocoding_nominatim import fetch_batch

        with patch(
            "app.services.providers.geocoding_nominatim.fetch_one",
            new_callable=AsyncMock,
            return_value=(("France", "Paris"), 200),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                results, stats = await fetch_batch([(48.85, 2.35)])

        assert results == [("France", "Paris")]
        assert stats[200] == 1

    @pytest.mark.asyncio
    async def test_multiple_points_with_delay(self):
        from app.services.providers.geocoding_nominatim import fetch_batch

        sleep_calls = []

        async def mock_sleep(s):
            sleep_calls.append(s)

        with patch(
            "app.services.providers.geocoding_nominatim.fetch_one",
            new_callable=AsyncMock,
            return_value=(None, 0),
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                results, stats = await fetch_batch([(1.0, 2.0), (3.0, 4.0)])

        # Should sleep between points (not after last one)
        assert len(sleep_calls) == 1
        assert len(results) == 2
