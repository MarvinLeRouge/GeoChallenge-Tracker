"""Tests for Utils functions (unit tests - no DB required)."""

from datetime import datetime, timezone

from app.core.utils import now, utcnow


class TestUtcnow:
    """Test utcnow function."""

    def test_utcnow_returns_utc(self):
        """Test that utcnow returns a timezone-aware datetime in UTC."""
        result = utcnow()

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_utcnow_is_current(self):
        """Test that utcnow returns current time."""
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)

        assert before <= result <= after

    def test_utcnow_timezone_aware(self):
        """Test that utcnow returns timezone-aware datetime."""
        result = utcnow()

        # Should be able to convert to other timezones
        result_iso = result.isoformat()
        assert "T" in result_iso
        assert "+" in result_iso or "Z" in result_iso or "-" in result_iso


class TestNow:
    """Test now function."""

    def test_now_returns_datetime(self):
        """Test that now returns a datetime object."""
        result = now()

        assert result is not None
        assert isinstance(result, datetime)

    def test_now_is_naive(self):
        """Test that now returns a naive datetime (no timezone)."""
        result = now()

        assert result.tzinfo is None

    def test_now_is_current(self):
        """Test that now returns current time."""
        before = datetime.now()
        result = now()
        after = datetime.now()

        assert before <= result <= after

    def test_now_vs_utcnow(self):
        """Test that now() and utcnow() are different (naive vs aware)."""
        local = now()
        utc = utcnow()

        assert local.tzinfo is None
        assert utc.tzinfo is not None
        assert utc.tzinfo == timezone.utc
