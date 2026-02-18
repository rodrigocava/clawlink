"""
ClawPulse — Rate limiter (shared instance)
Imported by main.py and all routers that apply @limiter.limit().
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """Use CF-Connecting-IP when behind Cloudflare, fall back to remote address."""
    return request.headers.get("CF-Connecting-IP") or get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)
