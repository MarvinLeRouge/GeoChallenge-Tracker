from collections.abc import Sequence

from fastapi import HTTPException, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.settings import get_settings

settings = get_settings()

_UPLOAD_READ_CHUNK_SIZE = 1024 * 1024  # 1 MB


async def read_upload_file_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Reads an UploadFile in chunks, enforcing a maximum cumulative size.

    Description:
        `MaxBodySizeMiddleware` only rejects requests carrying a `Content-Length`
        header over the limit - a chunked transfer-encoding request has no
        `Content-Length` at all and sails through it untouched. Routes that accept
        file uploads must therefore enforce their own cap while streaming the file,
        rather than trusting the middleware alone or reading the whole file in one
        unbounded `await file.read()`.

    Args:
        file (UploadFile): The uploaded file to read.
        max_bytes (int): Maximum allowed cumulative size, in bytes.

    Returns:
        bytes: The full file content (guaranteed <= max_bytes).

    Raises:
        HTTPException: 413 if the cumulative size exceeds max_bytes.
    """
    chunks: list[bytes] = []
    read_bytes = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        read_bytes += len(chunk)
        if read_bytes > max_bytes:
            await file.close()
            raise HTTPException(
                status_code=413,
                detail=f"File too large (>{max_bytes // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)
    await file.close()
    return b"".join(chunks)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int, exclude_paths: Sequence[str] = ()):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths

    async def dispatch(self, request, call_next):
        # Optional: exclude certain routes (e.g. /health)
        for p in self.exclude_paths:
            if request.url.path.startswith(p):
                return await call_next(request)

        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self.max_body_size:
                    return JSONResponse(
                        {
                            "detail": f"Fichier trop volumineux (>{self.max_body_size // settings.one_mb} Mo)."
                        },
                        status_code=413,
                    )
            except ValueError:
                # Invalid Content-Length — let it pass; the route will handle size checking during streaming
                pass
        return await call_next(request)
