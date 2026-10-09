# app/api/routes/maintenance/test_email.py
# Admin test-email route (POST /maintenance/test-email).

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from app.core.email import send_test_email
from app.core.settings import get_settings
from app.db.mongodb import get_collection

from ._router import router


@router.post(
    "/test-email",
    summary="Send a test email",
    description=(
        "Sends a test email to the specified address.\n\n"
        "The email includes the current date/time and basic database statistics "
        "(users, caches, challenges) to avoid spam filters."
    ),
)
async def test_email(
    to_email: Annotated[
        str | None, Query(description="Recipient email address. Defaults to ADMIN_TEST_EMAIL.")
    ] = None,
):
    """Sends a test email with basic app statistics.

    Args:
        to_email (str): Recipient email address.

    Returns:
        dict: Confirmation message and stats included in the email.
    """
    settings = get_settings()
    recipient = to_email or settings.admin_test_email

    coll_users = await get_collection("users")
    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")

    user_count = await coll_users.count_documents({})
    cache_count = await coll_caches.count_documents({})
    challenge_count = await coll_challenges.count_documents({})

    await send_test_email(
        to_email=recipient,
        user_count=user_count,
        cache_count=cache_count,
        challenge_count=challenge_count,
    )

    return {
        "message": f"Test email sent to {recipient}",
        "stats": {
            "users": user_count,
            "caches": cache_count,
            "challenges": challenge_count,
        },
    }
