"""
ClawPulse — System routes
  GET /health   liveness check
"""
from fastapi import APIRouter

from models import StatusResponse

router = APIRouter(tags=["System"])


@router.get("/health", response_model=StatusResponse, summary="Health check")
async def health_check():
    """Returns 200 OK if the server is running. Use for uptime monitoring."""
    return StatusResponse(status="ok", message="ClawPulse is running")
