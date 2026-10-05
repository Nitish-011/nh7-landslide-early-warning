from fastapi import Request
from slowapi import Limiter

def get_client_ip(request: Request) -> str:
    """Extract client IP, honoring X-Forwarded-For if available."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

# Shared rate limiter instance with default 120 requests/minute per IP
limiter = Limiter(key_func=get_client_ip, default_limits=["120/minute"])
