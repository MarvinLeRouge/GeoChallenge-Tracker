"""Tests for read_upload_file_with_limit (backend/app/core/middleware.py).

This is the streaming, in-route size guard that closes the gap left by
MaxBodySizeMiddleware: a chunked transfer-encoding request carries no
Content-Length header, so the middleware's check never triggers for it.
"""

import io

import pytest
from fastapi import HTTPException, UploadFile

from app.core.middleware import read_upload_file_with_limit


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="test.txt")


class TestReadUploadFileWithLimit:
    @pytest.mark.asyncio
    async def test_reads_full_content_within_limit(self):
        data = b"hello world"
        result = await read_upload_file_with_limit(_upload(data), max_bytes=1024)
        assert result == data

    @pytest.mark.asyncio
    async def test_raises_413_when_over_limit(self):
        data = b"x" * 100
        with pytest.raises(HTTPException) as exc_info:
            await read_upload_file_with_limit(_upload(data), max_bytes=50)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_exactly_at_limit_succeeds(self):
        data = b"x" * 50
        result = await read_upload_file_with_limit(_upload(data), max_bytes=50)
        assert result == data

    @pytest.mark.asyncio
    async def test_enforces_limit_across_multiple_chunks(self):
        # Larger than the internal 1MB chunk size, to exercise accumulation
        # across several reads rather than a single one.
        data = b"y" * (2 * 1024 * 1024)
        with pytest.raises(HTTPException) as exc_info:
            await read_upload_file_with_limit(_upload(data), max_bytes=1024 * 1024)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_closes_the_file(self):
        upload = _upload(b"x" * 100)
        await read_upload_file_with_limit(upload, max_bytes=1024)
        assert upload.file.closed
