from collections.abc import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.settings import get_settings
settings = get_settings()


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int, exclude_paths: Sequence[str] = ()):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths

    async def dispatch(self, request, call_next):
        # Optionnel: exclure certaines routes (ex. /health)
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
                # Content-Length invalide → on laisse passer, la route fera le contrôle en streaming
                pass
        return await call_next(request)
