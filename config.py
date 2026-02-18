"""
ClawPulse — Configuration
All settings are read from environment variables with sensible defaults.
"""
import os

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH         = os.getenv("DATABASE_PATH", "sync.db")

# ── Data retention ────────────────────────────────────────────────────────────
DATA_TTL_HOURS        = int(os.getenv("DATA_TTL_HOURS", "48"))
TTL_MIN_HOURS         = 1
TTL_MAX_HOURS         = 168   # 7 days

# ── Quotas ────────────────────────────────────────────────────────────────────
MAX_PAYLOAD_BYTES     = int(os.getenv("MAX_PAYLOAD_BYTES",      str(10 * 1024 * 1024)))  # 10 MB per upload
MAX_TOKEN_QUOTA_BYTES = int(os.getenv("MAX_TOKEN_QUOTA_BYTES",  str( 5 * 1024 * 1024)))  # 5 MB total per token

# ── Auth ──────────────────────────────────────────────────────────────────────
CLIENT_SECRET         = os.getenv("CLIENT_SECRET", "")  # Empty = dev mode (no auth)

# ── Background cleanup ────────────────────────────────────────────────────────
CLEANUP_INTERVAL_SEC  = int(os.getenv("CLEANUP_INTERVAL_SEC", str(60 * 60)))  # 1 hour

# ── Subscriptions ─────────────────────────────────────────────────────────────
REQUIRE_SUBSCRIPTION  = os.getenv("REQUIRE_SUBSCRIPTION", "false").lower() == "true"
# Set to "Sandbox" for TestFlight / development, "Production" for App Store
APPLE_ENVIRONMENT     = os.getenv("APPLE_ENVIRONMENT", "Production")
