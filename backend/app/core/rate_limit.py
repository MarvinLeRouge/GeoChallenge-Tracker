# backend/app/core/rate_limit.py
# Rate limiter for brute-force / spam protection on sensitive auth routes.

import inspect
from typing import Callable, TypeVar

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

LOGIN_RATE_LIMIT = "10/minute"
REGISTER_RATE_LIMIT = "5/minute"
RESEND_VERIFICATION_RATE_LIMIT = "3/minute"

F = TypeVar("F", bound=Callable)


def rate_limited(limit_value: str) -> Callable[[F], F]:
    """Applies a slowapi rate limit while keeping FastAPI dependency injection working.

    Description:
        `slowapi.Limiter.limit` wraps the route with `functools.wraps`, whose
        `__globals__` point at slowapi's own module, not the route module's. Combined
        with `from __future__ import annotations` (all annotations become strings),
        FastAPI can no longer resolve `Annotated[..., Depends(...)]` params on the
        wrapped function and silently treats them as query params instead. Restoring
        `__signature__` from the original, unwrapped function (resolved against its own
        module globals) fixes this.
    """

    def decorator(func: F) -> F:
        wrapped = limiter.limit(limit_value)(func)
        wrapped.__signature__ = inspect.signature(func, eval_str=True)
        return wrapped

    return decorator
