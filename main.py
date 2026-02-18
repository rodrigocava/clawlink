"""
ClawPulse Sync Server
====================
Encrypted data relay between the ClawPulse mobile app and any OpenClaw instance.

Privacy model: server stores only encrypted blobs. Plaintext never leaves the client.
All encryption/decryption happens on the edges (mobile app + OpenClaw).

GitHub: https://github.com/rodrigocava/clawpulse
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import CLEANUP_INTERVAL_SEC
from database import get_db, purge_all_expired
from limiter import limiter
from routers import subscription, sync, system


# ── Background cleanup ────────────────────────────────────────────────────────

async def _cleanup_loop() -> None:
    """Purge expired datapoints every CLEANUP_INTERVAL_SEC. Runs as a background task."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SEC)
        try:
            db = await get_db()
            try:
                deleted = await purge_all_expired(db)
                if deleted:
                    print(f"[cleanup] Purged {deleted} expired datapoint(s).", flush=True)
            finally:
                await db.close()
        except Exception as exc:
            print(f"[cleanup] Error during purge: {exc}", flush=True)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB + launch background cleanup
    db = await get_db()
    await db.close()
    task = asyncio.create_task(_cleanup_loop())
    yield
    # Shutdown: cancel background task cleanly
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    lifespan=lifespan,
    title="ClawPulse",
    description="""
Encrypted data relay for the **ClawPulse** mobile app (iOS & Android).

## How it works

1. The ClawPulse app encrypts your phone context data client-side
2. Encrypted blobs are uploaded here — the server **never sees plaintext**
3. Your OpenClaw instance fetches all blobs and decrypts them locally
4. Analysis and insights happen entirely on your own infrastructure

## Privacy

The server stores only opaque encrypted blobs keyed by a SHA-256 hash of your token.
Even with full database access, no personal data is recoverable without your password.

## Data retention

Each payload expires automatically after **48 hours** by default. Clients can override
per-upload via the `X-TTL-Hours` header (clamped to 1–168h).
Multiple datapoints accumulate over time — e.g. hourly sync = up to 48 datapoints.

## Self-hosting

The server is open source. Run your own at: https://github.com/rodrigocava/clawpulse
""",
    version="2.4.0",
    contact={"name": "ClawPulse", "url": "https://github.com/rodrigocava/clawpulse"},
    license_info={"name": "MIT"},
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(sync.router)
app.include_router(subscription.router)
app.include_router(system.router)
