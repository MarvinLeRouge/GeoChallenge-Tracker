"""Tests for progress.py: _ensure_uc_owned."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit._progress_test_helpers import (
    _UC_ID,
    _UID,
)


class TestEnsureUcOwned:
    """Test _ensure_uc_owned authorization check."""

    @pytest.mark.asyncio
    async def test_owned_returns_row(self):
        from app.services.progress import _ensure_uc_owned

        row = {"_id": _UC_ID}
        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=row)

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _ensure_uc_owned(_UID, _UC_ID)

        assert result == row

    @pytest.mark.asyncio
    async def test_not_owned_raises_permission_error(self):
        from app.services.progress import _ensure_uc_owned

        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=None)

        with patch("app.services.progress.get_collection", return_value=coll):
            with pytest.raises(PermissionError):
                await _ensure_uc_owned(_UID, _UC_ID)
