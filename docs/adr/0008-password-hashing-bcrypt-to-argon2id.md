# ADR 0008: Migrate password hashing from bcrypt to Argon2id

**Status:** Accepted
**Date:** 2026-08-02
**Deciders:** Marvin Le Rouge
**Sources:** PR #82 (`feat(backend): migrate password hashing from bcrypt to argon2id`)

## Context

Passwords were hashed with bcrypt, which remains ASVS-5.0-acceptable but is no longer OWASP's recommended default (OWASP A04 recommends Argon2id first). Bcrypt also silently truncates input to 72 bytes, a footgun that Argon2id does not share. Forcing every user to reset their password to move to a new hashing scheme was not acceptable.

## Decision

Migrate to Argon2id with transparent, gradual re-hashing rather than a forced reset:

- `pwd_context` (Passlib) is reconfigured as `CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")`: Argon2 is tried first and used for all new hashes, bcrypt stays accepted (but deprecated) so existing hashes keep verifying.
- A new `needs_rehash()` helper wraps Passlib's `needs_update()`.
- `POST /auth/login` calls `needs_rehash()` right after a successful password check; if the stored hash is a legacy bcrypt one, it is re-hashed to Argon2id and persisted immediately. Accounts migrate one login at a time, with no bulk migration job and no forced password reset.
- New hashes (registration, `seed_data.py`) use Argon2id from the same shared `CryptContext` instance, with no separate code path.
- Verified live in the dev stack: a test user was inserted with a real legacy bcrypt hash, logged in through the actual API, and the DB record was re-read to confirm `password_hash` changed from a `$2b$12$...` prefix to `$argon2id$v=19$m=655...`; the test user was cleaned up afterward.

## Consequences

- New and recently-active accounts get Argon2id automatically; accounts that never log in again keep their bcrypt hash indefinitely, since migration is login-triggered, not scheduled.
- No user-facing disruption: no forced password reset, no downtime for the change.
- The `CryptContext` now depends on both `argon2` and `bcrypt` verification support, both must be kept as dependencies as long as any legacy bcrypt hash could still exist.
- The 72-byte input truncation bug class is closed for every account once it has re-hashed to Argon2id, but not before.

## Alternatives considered

Not explicitly recorded in the source PR beyond the bcrypt-only state it replaces and the forced-reset approach it deliberately avoided ("no forced password reset" is stated as a design goal, not just a consequence).
