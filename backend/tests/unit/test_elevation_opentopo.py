"""Tests for app/services/providers/elevation_opentopo.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.providers.elevation_opentopo as mod

# ---------------------------------------------------------------------------
# _quota_key_for_today
# ---------------------------------------------------------------------------


class TestQuotaKeyForToday:
    def test_contains_provider_key(self):
        key = mod._quota_key_for_today()
        assert key.startswith("opentopodata_mapzen:")

    def test_date_format(self):
        key = mod._quota_key_for_today()
        # Format: opentopodata_mapzen:YYYY-MM-DD
        date_part = key.split(":")[1]
        assert len(date_part) == 10
        assert date_part[4] == "-" and date_part[7] == "-"


# ---------------------------------------------------------------------------
# _read_quota / _inc_quota
# ---------------------------------------------------------------------------


class TestReadQuota:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_doc(self):
        mock_coll = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value=None)

        with patch(
            "app.services.providers.elevation_opentopo.get_collection", return_value=mock_coll
        ):
            result = await mod._read_quota()

        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_doc_has_no_count(self):
        mock_coll = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value={"_id": "key"})

        with patch(
            "app.services.providers.elevation_opentopo.get_collection", return_value=mock_coll
        ):
            result = await mod._read_quota()

        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_count_from_doc(self):
        mock_coll = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value={"_id": "key", "count": 42})

        with patch(
            "app.services.providers.elevation_opentopo.get_collection", return_value=mock_coll
        ):
            result = await mod._read_quota()

        assert result == 42


class TestIncQuota:
    @pytest.mark.asyncio
    async def test_calls_update_one(self):
        mock_coll = AsyncMock()
        mock_coll.update_one = AsyncMock()

        with patch(
            "app.services.providers.elevation_opentopo.get_collection", return_value=mock_coll
        ):
            await mod._inc_quota(3)

        mock_coll.update_one.assert_called_once()
        call_kwargs = mock_coll.update_one.call_args
        assert call_kwargs[1].get("upsert") is True


# ---------------------------------------------------------------------------
# _build_param
# ---------------------------------------------------------------------------


class TestBuildParam:
    def test_single_point(self):
        result = mod._build_param([(48.85, 2.35)])
        assert result == "48.85,2.35"

    def test_multiple_points_pipe_separated(self):
        result = mod._build_param([(1.0, 2.0), (3.0, 4.0)])
        assert result == "1.0,2.0|3.0,4.0"

    def test_empty_list(self):
        assert mod._build_param([]) == ""


# ---------------------------------------------------------------------------
# _split_params_by_url_and_count
# ---------------------------------------------------------------------------


class TestSplitParamsByUrlAndCount:
    def test_empty_returns_empty(self):
        assert mod._split_params_by_url_and_count("") == []

    def test_single_point_single_chunk(self):
        chunks = mod._split_params_by_url_and_count("48.85,2.35")
        assert chunks == ["48.85,2.35"]

    def test_splits_by_url_length(self):
        # Force a very short max_param_len by patching URL_MAXLEN and ENDPOINT
        with (
            patch.object(mod, "URL_MAXLEN", 30),
            patch.object(mod, "ENDPOINT", "http://x"),
        ):
            # prefix "http://x?locations=" = 21 chars -> max_param_len = 9
            param = "1.0,2.0|3.0,4.0|5.0,6.0"
            chunks = mod._split_params_by_url_and_count(param)
            assert len(chunks) > 1

    def test_splits_by_max_points(self):
        # 5 points, MAX_POINTS_PER_REQ = 2 → should produce multiple chunks
        with patch.object(mod, "MAX_POINTS_PER_REQ", 2):
            param = "1,1|2,2|3,3|4,4|5,5"
            chunks = mod._split_params_by_url_and_count(param)
            # Each chunk should have at most 2 points (1 pipe)
            for c in chunks:
                assert c.count("|") < 2

    def test_no_pipe_in_take_handled(self):
        """When rfind returns -1 (no pipe in the truncated slice)."""
        with (
            patch.object(mod, "URL_MAXLEN", 10),
            patch.object(mod, "ENDPOINT", ""),
        ):
            # prefix "" + "?locations=" = 11 chars → max_param_len = max(1, 10-11) = 1
            param = "48.85,2.35"
            chunks = mod._split_params_by_url_and_count(param)
            assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestFetch:
    @pytest.mark.asyncio
    async def test_returns_nones_when_disabled(self):
        with patch.object(mod, "ENABLED", False):
            result = await mod.fetch([(1.0, 2.0), (3.0, 4.0)])
        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_returns_nones_for_empty_points(self):
        with patch.object(mod, "ENABLED", True):
            result = await mod.fetch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_nones_when_quota_reached(self):
        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=9999,
            ),
            patch("os.getenv", return_value="1000"),
        ):
            result = await mod.fetch([(48.85, 2.35)])
        assert result == [None]

    @pytest.mark.asyncio
    async def test_returns_elevation_on_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"results": [{"elevation": 150.7}]})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(48.85, 2.35)])

        assert result == [151]

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(48.85, 2.35)])

        assert result == [None]

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(48.85, 2.35)])

        assert result == [None]

    @pytest.mark.asyncio
    async def test_none_elevation_in_response(self):
        """elevation field missing/None → None in result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"results": [{"elevation": None}]})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(48.85, 2.35)])

        assert result == [None]

    @pytest.mark.asyncio
    async def test_multiple_chunks_rate_limited(self):
        """Two chunks → asyncio.sleep called once (between chunks)."""
        sleep_calls = []

        async def mock_sleep(s):
            sleep_calls.append(s)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"results": []})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Force two distinct chunks by patching the split function directly
        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._split_params_by_url_and_count",
                return_value=["1.0,2.0", "3.0,4.0"],
            ),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", side_effect=mock_sleep),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(1.0, 2.0), (3.0, 4.0)])

        # One sleep between the two chunks
        assert len(sleep_calls) == 1
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_quota_stops_mid_loop(self):
        """If daily_count reaches DAILY_LIMIT mid-loop, breaks early."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"results": []})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # 3 chunks, daily starts at 999, DAILY_LIMIT=1000:
        # chunk 0: 999 < 1000 → process, daily becomes 1000
        # chunk 1: 1000 >= 1000 → break (line 222 hit)
        with (
            patch.object(mod, "ENABLED", True),
            patch(
                "app.services.providers.elevation_opentopo._split_params_by_url_and_count",
                return_value=["1.0,2.0", "3.0,4.0", "5.0,6.0"],
            ),
            patch(
                "app.services.providers.elevation_opentopo._read_quota",
                new_callable=AsyncMock,
                return_value=999,
            ),
            patch("app.services.providers.elevation_opentopo._inc_quota", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await mod.fetch([(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)])

        # Only the first chunk ran; remaining slots stay None
        assert len(result) == 3
        assert mock_client.get.call_count == 1
