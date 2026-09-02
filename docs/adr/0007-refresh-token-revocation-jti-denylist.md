# ADR 0007: Refresh token revocation via JTI denylist and explicit logout

**Status:** Accepted
**Date:** 2026-08-01
**Deciders:** Marvin Le Rouge
**Sources:** PR #66 (`feat(auth): add server-side refresh token revocation and logout endpoint`)

## Context

Refresh tokens were valid for their full lifetime with no server-side way to invalidate one early: there was no logout endpoint that actually revoked anything server-side, so a token that leaked (or a user wanting to log out from a compromised session) stayed usable until natural expiry. Separately, the `refresh_token` cookie's path was scoped to `/auth/refresh`, which meant it wasn't even sent to a hypothetical `/auth/logout` endpoint at another path.

## Decision

Add explicit, server-enforced refresh token revocation:

- Every refresh token now carries a unique `jti` claim.
- `POST /auth/refresh` checks the presented token's `jti` against a TTL-backed denylist collection and rejects revoked tokens.
- A new `POST /auth/logout` endpoint revokes the current refresh token (adds its `jti` to the denylist) and clears the cookie; it is idempotent and does not require a valid access token, so logout works even with an expired access token.
- The `refresh_token` cookie's path is corrected from `/auth/refresh` to `/auth`, so it is actually sent to `/auth/logout`.
- The frontend auth store calls the logout endpoint on logout (best-effort) instead of only clearing local state, so logout is server-effective, not just client-side.

## Consequences

- A refresh token can now be invalidated before its natural expiry, both on explicit logout and, going forward, for other revocation triggers (e.g. a future "log out all sessions" action) that reuse the same denylist.
- The denylist collection needs a TTL index to avoid growing unbounded with revoked-but-expired entries; this was included as part of the change.
- `/auth/refresh` now does one more lookup (denylist check) per call, a small added cost for the revocation guarantee.
- Logout is meaningful without requiring a valid access token, matching the common case of a user logging out after their access token has already expired.

## Alternatives considered

Not explicitly recorded in the source PR beyond the no-revocation state it replaces (refresh tokens valid until natural expiry, logout only clearing client-side state). No evidence of a documented comparison against alternatives such as short-lived refresh tokens without a denylist, or a full session-store model.
