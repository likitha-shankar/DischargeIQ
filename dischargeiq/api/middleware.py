"""
api/middleware.py

Production security middleware for DischargeIQ.

Three concerns are handled here:
    SecurityHeadersMiddleware — adds defensive HTTP headers to every response.
    RateLimitMiddleware       — in-process token-bucket per client IP for /analyze and /chat.
    verify_api_key            — FastAPI dependency; enforces Bearer token when
                                DISCHARGEIQ_API_KEY is set in the environment.

Why in-process rate limiting instead of Redis:
    DischargeIQ runs as a single-container demo on Cloud Run min-instances=1.
    A per-process sliding window is sufficient to prevent runaway cost attacks
    from a single bad actor. Production scale-out would need Redis-backed
    counting (e.g. via slowapi + Redis), but that is out of scope for this phase.
    The in-process limiter still provides meaningful protection: each LLM call
    costs real money and the 300s pipeline budget means a single /analyze
    request holds a thread for up to 5 minutes.

Dependencies:
    starlette (bundled with FastAPI)
    dischargeiq.utils.logger (shared logger config — no circular import)
"""

import logging
import os
import re
import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Security headers ──────────────────────────────────────────────────────────

# Headers added to every response. Content-Security-Policy is intentionally
# omitted here because Streamlit requires 'unsafe-inline' and Cloud Run's load
# balancer injects its own; adding a strict CSP from FastAPI would break the UI.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Prevents caching of sensitive health/progress responses on shared proxies.
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add defensive HTTP response headers to every FastAPI response.

    Placed before CORS middleware so headers are injected on all responses
    including preflight (OPTIONS) and error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Forward the request and add security headers to the response.

        Args:
            request:   Incoming HTTP request.
            call_next: Next middleware or route handler in the chain.

        Returns:
            Response: The route response with security headers appended.
        """
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


# ── Rate limiting ─────────────────────────────────────────────────────────────

# Limits per endpoint:
#   /analyze: expensive (4-6 LLM calls, up to 30s). Cap at 5 req/min per IP.
#   /chat:    cheap (1 LLM call, ~2s). Cap at 30 req/min per IP.
# Window: sliding 60-second window using a simple token-replenishment approach.
_RATE_LIMITS: dict[str, tuple[int, float]] = {
    "/analyze": (5, 60.0),    # max_requests, window_seconds
    "/chat": (30, 60.0),
}

_rate_lock = threading.Lock()
# Structure: {endpoint: {ip: [timestamp, ...]}}
_rate_windows: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-process per-IP, per-endpoint sliding-window rate limiter.

    Applied only to expensive endpoints (/analyze, /chat). All other endpoints
    are unthrottled. On limit breach, returns HTTP 429 with a Retry-After
    header indicating when the oldest request will age out of the window.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Check rate limit before forwarding the request.

        Args:
            request:   Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            JSONResponse (429) when the limit is exceeded.
            Otherwise the route's response.
        """
        path = request.url.path
        if path not in _RATE_LIMITS:
            return await call_next(request)

        max_requests, window = _RATE_LIMITS[path]
        fwd = request.headers.get("X-Forwarded-For", "")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
        now = time.monotonic()
        cutoff = now - window

        with _rate_lock:
            timestamps = _rate_windows[path][ip]
            # Evict requests outside the sliding window.
            _rate_windows[path][ip] = [t for t in timestamps if t > cutoff]
            if len(_rate_windows[path][ip]) >= max_requests:
                oldest = _rate_windows[path][ip][0]
                retry_after = int(oldest + window - now) + 1
                logger.warning(
                    "Rate limit hit — IP: %s, path: %s, limit: %d/%ds",
                    ip, path, max_requests, int(window),
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Too many requests. Limit: {max_requests} per "
                            f"{int(window)}s. Retry after {retry_after}s."
                        )
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            _rate_windows[path][ip].append(now)

        return await call_next(request)


# ── API key authentication ────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)

# Module-level compiled pattern for filename sanitization — shared with routes.
# Strips newlines, carriage returns, tabs, and ANSI escape sequences so that
# user-controlled filenames cannot contaminate structured logs or forge entries.
_LOG_UNSAFE_CHARS = re.compile(r"[\r\n\t]|\x1b\[[0-9;]*[mGKH]")


def sanitize_for_log(value: str, max_len: int = 255) -> str:
    """
    Strip log-unsafe characters from a user-controlled string.

    Removes:
        - Newlines and carriage returns (log injection / forged entries)
        - Tabs (log field separator injection)
        - ANSI escape sequences (terminal hijacking via log tailing)

    Args:
        value:   Raw user-supplied string (e.g. uploaded filename).
        max_len: Maximum length of the returned string.

    Returns:
        str: Sanitized string safe for inclusion in log messages.
    """
    return _LOG_UNSAFE_CHARS.sub("_", value)[:max_len]


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> None:
    """
    FastAPI dependency: enforce Bearer token when DISCHARGEIQ_API_KEY is set.

    When DISCHARGEIQ_API_KEY is not set, the check is skipped (open dev mode).
    When set, requests without a valid token receive HTTP 401.

    Use with Depends() on individual route functions or entire APIRouter:
        router = APIRouter(dependencies=[Depends(verify_api_key)])

    The key is compared with hmac.compare_digest to prevent timing attacks.

    Args:
        credentials: Parsed Authorization header from HTTPBearer.

    Raises:
        HTTPException 401: When the key is required but missing or wrong.
    """
    import hmac

    required_key = os.environ.get("DISCHARGEIQ_API_KEY", "").strip()
    if not required_key:
        return  # Dev mode: no key configured → open access

    token = credentials.credentials if credentials else ""
    if not hmac.compare_digest(token.encode(), required_key.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set Authorization: Bearer <key>.",
        )
