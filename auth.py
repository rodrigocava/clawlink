"""
ClawPulse — Auth dependencies
  - verify_client_secret: shared app secret header (blocks unauthenticated requests)
  - check_subscription:   validates active subscription when REQUIRE_SUBSCRIPTION=true
"""
import aiosqlite
from fastapi import Header, HTTPException

from config import CLIENT_SECRET, REQUIRE_SUBSCRIPTION
from database import now_utc


async def verify_client_secret(x_clawpulse_secret: str = Header(default="")) -> None:
    """
    Validate the shared app secret sent in every request.
    Set CLIENT_SECRET env var to enable. If unset, validation is skipped (dev mode).
    """
    if CLIENT_SECRET and x_clawpulse_secret != CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing client secret.")


async def check_subscription(db: aiosqlite.Connection, token_hash: str) -> None:
    """
    Raise 402 Payment Required if REQUIRE_SUBSCRIPTION is enabled
    and the token has no active subscription in the subscribers table.
    No-op when REQUIRE_SUBSCRIPTION=false (default for self-hosted).
    """
    if not REQUIRE_SUBSCRIPTION:
        return

    async with db.execute(
        "SELECT active_until FROM subscribers WHERE token_hash = ? AND active_until > ?",
        (token_hash, now_utc()),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=402,
            detail="Active subscription required. Please subscribe in the ClawPulse app.",
        )
