"""
ClawPulse — Sync routes
  POST   /sync           upload encrypted payload
  GET    /sync/{token}   fetch all datapoints
  GET    /sync/{token}/count  count datapoints (no payload data)
  DELETE /sync/{token}   wipe all datapoints for a token
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from auth import check_subscription, verify_client_secret
from database import (
    check_quota,
    expiry_utc,
    get_db,
    hash_token,
    now_utc,
    parse_ttl_header,
    purge_expired_for_token,
)
from limiter import limiter
from models import CountResponse, Datapoint, StatusResponse, SyncResponse, SyncUpload

router = APIRouter(tags=["Sync"])


@router.post("/sync", response_model=StatusResponse, summary="Upload encrypted payload",
             dependencies=[Depends(verify_client_secret)])
@limiter.limit("10/minute")
async def upload_sync(
    request: Request,
    data: SyncUpload,
    x_ttl_hours: str | None = Header(default=None),
):
    """
    Upload an encrypted payload. Each upload creates a **new datapoint** — previous
    uploads are not replaced.

    - **token**: Your UUID (only its SHA-256 hash is stored)
    - **payload**: Base64-encoded AES-256-GCM encrypted blob
    - **X-TTL-Hours** *(optional header)*: Datapoint lifetime in hours, clamped to [1, 168].
      Defaults to `DATA_TTL_HOURS` (48h) if omitted or invalid.
    """
    ttl_hours  = parse_ttl_header(x_ttl_hours)
    token_hash = hash_token(data.token)
    db = await get_db()
    try:
        await check_subscription(db, token_hash)
        await purge_expired_for_token(db, token_hash)
        await check_quota(db, token_hash, data.payload)
        await db.execute(
            "INSERT INTO sync_data (token_hash, payload, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, data.payload, now_utc(), expiry_utc(ttl_hours)),
        )
        await db.commit()
    finally:
        await db.close()

    return StatusResponse(status="ok", message=f"Stored. Expires in {ttl_hours}h.")


@router.get("/sync/{token}", response_model=SyncResponse, summary="Fetch all datapoints",
            dependencies=[Depends(verify_client_secret)])
@limiter.limit("30/minute")
async def fetch_sync(request: Request, token: str):
    """
    Retrieve all non-expired datapoints for a token, ordered oldest → newest.

    Returns an array of encrypted blobs — decryption happens on your OpenClaw instance.
    Returns **404** if no data exists or all datapoints have expired.
    """
    token_hash = hash_token(token)
    db = await get_db()
    try:
        await purge_expired_for_token(db, token_hash)
        async with db.execute(
            "SELECT payload, created_at, expires_at FROM sync_data "
            "WHERE token_hash = ? AND expires_at > ? ORDER BY created_at ASC",
            (token_hash, now_utc()),
        ) as cursor:
            rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for this token (may have expired or never been uploaded).",
        )

    return SyncResponse(
        count=len(rows),
        datapoints=[Datapoint(payload=r[0], created_at=r[1], expires_at=r[2]) for r in rows],
    )


@router.get("/sync/{token}/count", response_model=CountResponse, summary="Count datapoints",
            dependencies=[Depends(verify_client_secret)])
@limiter.limit("30/minute")
async def count_sync(request: Request, token: str):
    """
    Returns the number of non-expired datapoints plus oldest/newest timestamps.
    No payload data is returned — useful for the app dashboard.
    """
    token_hash = hash_token(token)
    db = await get_db()
    try:
        await purge_expired_for_token(db, token_hash)
        async with db.execute(
            "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM sync_data "
            "WHERE token_hash = ? AND expires_at > ?",
            (token_hash, now_utc()),
        ) as cursor:
            row = await cursor.fetchone()
    finally:
        await db.close()

    count, oldest, newest = row if row else (0, None, None)
    return CountResponse(count=count, oldest=oldest, newest=newest)


@router.delete("/sync/{token}", response_model=StatusResponse, summary="Delete all datapoints",
               dependencies=[Depends(verify_client_secret)])
@limiter.limit("10/minute")
async def delete_sync(request: Request, token: str):
    """Delete **all** datapoints for a token (the app's Nuke button)."""
    token_hash = hash_token(token)
    db = await get_db()
    try:
        result = await db.execute(
            "DELETE FROM sync_data WHERE token_hash = ?", (token_hash,)
        )
        await db.commit()
        deleted = result.rowcount
    finally:
        await db.close()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="No data found for this token.")

    return StatusResponse(status="ok", message=f"Deleted {deleted} datapoint(s).")
