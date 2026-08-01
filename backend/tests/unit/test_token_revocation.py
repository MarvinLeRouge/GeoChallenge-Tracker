"""Tests for app.core.token_revocation: the refresh-token denylist."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.token_revocation import is_refresh_token_revoked, revoke_refresh_token


def _mock_collection(*, found: dict | None = None) -> MagicMock:
    coll = MagicMock()
    coll.update_one = AsyncMock(return_value=None)
    coll.find_one = AsyncMock(return_value=found)
    return coll


class TestRevokeRefreshToken:
    @pytest.mark.asyncio
    async def test_upserts_jti_with_expiry(self):
        coll = _mock_collection()
        expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)

        with patch(
            "app.core.token_revocation.get_collection",
            AsyncMock(return_value=coll),
        ):
            await revoke_refresh_token("some-jti", expires_at)

        coll.update_one.assert_awaited_once_with(
            {"jti": "some-jti"},
            {"$set": {"jti": "some-jti", "expires_at": expires_at}},
            upsert=True,
        )


class TestIsRefreshTokenRevoked:
    @pytest.mark.asyncio
    async def test_returns_true_when_found(self):
        coll = _mock_collection(found={"_id": "x"})

        with patch(
            "app.core.token_revocation.get_collection",
            AsyncMock(return_value=coll),
        ):
            result = await is_refresh_token_revoked("revoked-jti")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        coll = _mock_collection(found=None)

        with patch(
            "app.core.token_revocation.get_collection",
            AsyncMock(return_value=coll),
        ):
            result = await is_refresh_token_revoked("unknown-jti")

        assert result is False
