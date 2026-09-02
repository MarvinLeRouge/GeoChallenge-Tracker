# ADR 0006: Rate limiting on auth endpoints via slowapi

**Status:** Accepted
**Date:** 2026-08-01
**Deciders:** Marvin Le Rouge
**Sources:** PR #65 (`fix(backend): add rate limiting on auth endpoints`)

## Context

The security hardening pass identified that `/auth/login`, `/auth/register`, and `/auth/resend-verification` had no rate limiting, leaving them open to brute-force credential guessing and registration/verification-email spam.

## Decision

Add `slowapi` (a FastAPI-compatible wrapper around `limits`) as the rate-limiting layer for sensitive auth routes:

- A shared `Limiter` (`backend/app/core/rate_limit.py`), keyed by remote address, is registered on the FastAPI app.
- Per-route limits: `/auth/login` at 10/min, `/auth/register` at 5/min, `/auth/resend-verification` at 3/min.
- A custom `RateLimitExceeded` handler (`backend/app/core/exception_handlers.py`) returns a `429` with a `Retry-After` header, in the project's standard `ErrorResponse` format rather than slowapi's default error body.
- Because `slowapi.Limiter.limit` wraps the route with `functools.wraps`, whose `__globals__` point at slowapi's own module instead of the route module's, a small wrapper in `rate_limit.py` applies the limit while keeping FastAPI's dependency injection working correctly.

## Consequences

- Brute-force login attempts and registration/verification spam are now bounded per source IP, not just theoretically discouraged.
- Rate-limit state is in-process (via `slowapi`/`limits`' default backend), so it is per-worker unless a shared backend (e.g. Redis) is configured; this was not part of this change.
- Legitimate users behind a shared IP (NAT, corporate proxy) can be affected by the same per-IP limit as an attacker; no allowlist or alternate keying was introduced.

## Alternatives considered

Not explicitly recorded in the source PR beyond the no-rate-limiting state it replaces. No evidence of a documented comparison between `slowapi` and other rate-limiting approaches (e.g. reverse-proxy-level limiting in Traefik) at decision time.
