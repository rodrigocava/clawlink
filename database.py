"""
ClawPulse — Database helpers
Handles connection, table creation, token hashing, TTL, purge, and quota checks.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import HTTPException

from config import (
    DATABASE_PATH,
    DATA_TTL_HOURS,
    MAX_PAYLOAD_BYTES,
    MAX_TOKEN_QUOTA_BYTES,
    TTL_MIN_HOURS,
    TTL_MAX_HOURS,
)


# ── Connection ────────────────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sync_data (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash  TEXT NOT NULL,
            payload     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_token_hash ON sync_data(token_hash)")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            token_hash               TEXT PRIMARY KEY,
            active_until             TEXT NOT NULL,
            original_transaction_id  TEXT NOT NULL UNIQUE,
            environment              TEXT NOT NULL DEFAULT 'Production',
            created_at               TEXT NOT NULL,
            updated_at               TEXT NOT NULL
        )
    """)
    await db.commit()
    return db


# ── Utilities ─────────────────────────────────────────────────────────────────

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def expiry_utc(ttl_hours: int = DATA_TTL_HOURS) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()


def parse_ttl_header(value: str | None) -> int:
    """Parse X-TTL-Hours header. Clamps to [TTL_MIN, TTL_MAX]. Falls back to DATA_TTL_HOURS."""
    if value is None:
        return DATA_TTL_HOURS
    try:
        return max(TTL_MIN_HOURS, min(int(value), TTL_MAX_HOURS))
    except (ValueError, TypeError):
        return DATA_TTL_HOURS


# ── Purge ─────────────────────────────────────────────────────────────────────

async def purge_expired_for_token(db: aiosqlite.Connection, token_hash: str) -> None:
    """Remove expired rows for a specific token."""
    await db.execute(
        "DELETE FROM sync_data WHERE token_hash = ? AND expires_at < ?",
        (token_hash, now_utc()),
    )
    await db.commit()


async def purge_all_expired(db: aiosqlite.Connection) -> int:
    """Remove all expired rows across all tokens. Returns number of rows deleted."""
    cursor = await db.execute(
        "DELETE FROM sync_data WHERE expires_at < ?", (now_utc(),)
    )
    await db.commit()
    return cursor.rowcount


# ── Quota ─────────────────────────────────────────────────────────────────────

async def check_quota(db: aiosqlite.Connection, token_hash: str, new_payload: str) -> None:
    """Enforce per-token total storage quota across all active datapoints."""
    new_size = len(new_payload.encode())
    if new_size > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Payload exceeds single upload size limit.")

    async with db.execute(
        "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM sync_data WHERE token_hash = ? AND expires_at > ?",
        (token_hash, now_utc()),
    ) as cursor:
        row = await cursor.fetchone()
        current_total = row[0] if row else 0

    if current_total + new_size > MAX_TOKEN_QUOTA_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Token storage quota exceeded ({MAX_TOKEN_QUOTA_BYTES // 1024 // 1024}MB total). "
                "Old datapoints will free up space as they expire."
            ),
        )
