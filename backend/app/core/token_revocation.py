# backend/app/core/token_revocation.py
# Server-side revocation (denylist) for refresh tokens, keyed by their JWT `jti` claim.

import datetime as dt

from app.db.mongodb import get_collection

REVOKED_REFRESH_TOKENS_COLLECTION = "revoked_refresh_tokens"


async def revoke_refresh_token(jti: str, expires_at: dt.datetime) -> None:
    """Marks a refresh token as revoked until its natural expiration.

    Description:
        Upserts `jti` into the denylist with `expires_at` set to the token's own `exp`
        claim, so the entry is auto-cleaned by MongoDB's TTL index once the token would
        have expired anyway (see `ensure_indexes` in `app.db.seed_indexes`).

    Args:
        jti (str): Unique identifier of the refresh token (`jti` claim).
        expires_at (datetime.datetime): The token's own expiration.

    Returns:
        None
    """
    coll = await get_collection(REVOKED_REFRESH_TOKENS_COLLECTION)
    await coll.update_one(
        {"jti": jti},
        {"$set": {"jti": jti, "expires_at": expires_at}},
        upsert=True,
    )


async def is_refresh_token_revoked(jti: str) -> bool:
    """Checks whether a refresh token has been revoked.

    Args:
        jti (str): Unique identifier of the refresh token (`jti` claim).

    Returns:
        bool: True if the token was revoked, False otherwise.
    """
    coll = await get_collection(REVOKED_REFRESH_TOKENS_COLLECTION)
    doc = await coll.find_one({"jti": jti}, {"_id": 1})
    return doc is not None
