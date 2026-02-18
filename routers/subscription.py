"""
ClawPulse — Subscription routes
  POST /activate   verify StoreKit 2 JWS + register subscriber
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from apple_jws import verify_apple_jws
from config import APPLE_ENVIRONMENT
from database import get_db, hash_token, now_utc
from limiter import limiter
from models import ActivateRequest, StatusResponse

router = APIRouter(tags=["Subscription"])


@router.post("/activate", response_model=StatusResponse, summary="Activate subscription")
@limiter.limit("5/minute")
async def activate_subscription(request: Request, data: ActivateRequest):
    """
    Activate or renew a subscription by verifying a StoreKit 2 signed transaction.

    The iOS app should call this endpoint:
    - After a successful in-app purchase
    - On every app launch (to refresh `active_until` after a renewal)

    **JWS verification steps:**
    1. Decode x5c certificate chain from JWS header
    2. Verify each cert is signed by the next
    3. Verify chain root traces to Apple Root CA G3
    4. Verify JWS signature with the leaf cert's public key
    5. Verify `appAccountToken` in JWS matches the provided `token`

    **Self-hosted:** Available but `REQUIRE_SUBSCRIPTION=false` means subscription
    status is never checked on sync endpoints.
    """
    # ── Verify JWS ───────────────────────────────────────────────────────────
    try:
        payload = await verify_apple_jws(data.jws_transaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JWS transaction: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JWS verification failed: {e}")

    # ── Extract + validate payload fields ─────────────────────────────────────
    app_account_token = payload.get("appAccountToken")
    if not app_account_token:
        raise HTTPException(
            status_code=400,
            detail="JWS missing appAccountToken — was it set during purchase?",
        )
    if app_account_token.lower() != data.token.lower():
        raise HTTPException(
            status_code=400,
            detail="appAccountToken in JWS does not match provided token.",
        )

    original_transaction_id = payload.get("originalTransactionId")
    if not original_transaction_id:
        raise HTTPException(status_code=400, detail="JWS missing originalTransactionId.")

    expires_ms = payload.get("expiresDate")
    if not expires_ms:
        raise HTTPException(
            status_code=400,
            detail="JWS missing expiresDate — is this a subscription product?",
        )

    active_until = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc).isoformat()
    environment  = payload.get("environment", "Production")

    # ── Reject Sandbox transactions in Production mode ────────────────────────
    if APPLE_ENVIRONMENT == "Production" and environment == "Sandbox":
        raise HTTPException(
            status_code=400,
            detail="Sandbox transactions not accepted in Production mode.",
        )

    # ── Upsert subscriber record ──────────────────────────────────────────────
    token_hash = hash_token(data.token)
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO subscribers
                (token_hash, active_until, original_transaction_id, environment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_hash) DO UPDATE SET
                active_until            = excluded.active_until,
                original_transaction_id = excluded.original_transaction_id,
                environment             = excluded.environment,
                updated_at              = excluded.updated_at
            """,
            (token_hash, active_until, original_transaction_id, environment, now_utc(), now_utc()),
        )
        await db.commit()
    finally:
        await db.close()

    return StatusResponse(
        status="ok",
        message=f"Subscription activated. Active until {active_until} ({environment}).",
    )
