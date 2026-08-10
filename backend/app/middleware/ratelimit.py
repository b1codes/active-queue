from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.envelopes import ErrorBody, ErrorEnvelope

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Fixed window size in seconds
WINDOW_SECONDS = settings.rate_limit_window_seconds

# Base rate limits per SPEC §14.4 & Task 86bbay4ve requirements
LIMIT_GENERAL = settings.rate_limit_general  # 60 req/min default
LIMIT_SYNC = settings.rate_limit_sync  # 10 req/min default on sync trigger endpoints
LIMIT_HEAVY = settings.rate_limit_heavy  # 30 req/min default on heavy/write endpoints

# Role limit multipliers per user tier
ROLE_LIMIT_MULTIPLIERS: dict[str, float] = {
    "anonymous": 0.5,  # Unauthenticated IP requests (30 general, 5 sync, 15 heavy)
    "user": 1.0,  # Standard authenticated user (60 general, 10 sync, 30 heavy)
    "premium": 2.0,  # Premium tier user (120 general, 20 sync, 60 heavy)
    "admin": 3.0,  # Admin tier user (180 general, 30 sync, 90 heavy)
}


def _get_endpoint_category(method: str, path: str) -> str:
    """Categorize API endpoints into health, sync, heavy, or general rate limit buckets."""
    if path == "/healthz":
        return "health"
    if method == "POST" and path.endswith("/sync"):
        return "sync"
    if (
        method in ("POST", "PUT", "DELETE") and ("/sources" in path or "/sessions" in path)
    ) or path.endswith("/match"):
        return "heavy"
    return "general"


def _extract_identity(request: Request) -> tuple[str, str]:
    """Safely extract user identifier (uid or IP) and role for rate limiting context."""
    uid = getattr(request.state, "uid", None)
    role = getattr(request.state, "role", None)
    has_auth_header = False

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        has_auth_header = True
        if not uid:
            token = auth_header[7:].strip()
            parts = token.split(".")
            if len(parts) == 3:
                try:
                    payload_b64 = parts[1]
                    rem = len(payload_b64) % 4
                    if rem:
                        payload_b64 += "=" * (4 - rem)
                    payload_bytes = base64.urlsafe_b64decode(payload_b64)
                    claims = json.loads(payload_bytes)
                    if isinstance(claims, dict):
                        extracted_uid = (
                            claims.get("uid") or claims.get("user_id") or claims.get("sub")
                        )
                        if extracted_uid and isinstance(extracted_uid, str):
                            uid = extracted_uid
                        if not role and claims.get("role") and isinstance(claims.get("role"), str):
                            role = claims.get("role")
                except Exception:
                    pass

    if uid:
        request.state.uid = uid
        user_role = role or "user"
        request.state.role = user_role
        return f"uid:{uid}", user_role

    client_ip = request.client.host if (request.client and request.client.host) else "anonymous"
    user_role = role or ("user" if has_auth_header else "anonymous")
    request.state.role = user_role
    return f"ip:{client_ip}", user_role


class FixedWindowRateLimiter:
    """Instance-local fixed-window in-memory rate limiter per SPEC §14.4.

    Enforces rate limits based on endpoint category and user role tiers.
    """

    def __init__(self) -> None:
        # Key: (identifier, category, window_start_time) -> count
        self._counts: dict[tuple[str, str, int], int] = {}
        self._last_cleanup = time.time()

    def check_and_increment(
        self,
        identifier: str,
        is_sync_endpoint: bool = False,
        now: float | None = None,
        role: str | None = None,
        category: str | None = None,
        custom_limit: int | None = None,
    ) -> tuple[bool, int, int, int]:
        """Check and increment request count for identifier in current fixed window.

        Returns tuple of:
        (is_allowed: bool, limit: int, remaining: int, reset_seconds: int)
        """
        current_time = now if now is not None else time.time()
        window_seconds = settings.rate_limit_window_seconds
        window_start = int(current_time) // window_seconds * window_seconds
        reset_seconds = max(1, int(window_start + window_seconds - current_time))

        if category is None:
            category = "sync" if is_sync_endpoint else "general"

        if role is None:
            if identifier.startswith("uid:") or identifier.startswith("user"):
                role = "user"
            elif identifier.startswith("ip:") or identifier == "anonymous":
                role = "anonymous"
            else:
                role = "user"

        if custom_limit is not None:
            limit = custom_limit
        else:
            base_limit = (
                settings.rate_limit_sync
                if category == "sync"
                else (
                    settings.rate_limit_heavy
                    if category == "heavy"
                    else settings.rate_limit_general
                )
            )
            multiplier = ROLE_LIMIT_MULTIPLIERS.get(role, 1.0)
            limit = max(1, int(base_limit * multiplier))

        key = (identifier, category, window_start)

        current_count = self._counts.get(key, 0)
        if current_count >= limit:
            remaining = 0
            return False, limit, remaining, reset_seconds

        new_count = current_count + 1
        self._counts[key] = new_count
        remaining = max(0, limit - new_count)

        # Cleanup stale windows every 2 minutes
        if current_time - self._last_cleanup > 120:
            self._cleanup(current_time)

        return True, limit, remaining, reset_seconds

    def _cleanup(self, current_time: float) -> None:
        """Prune windows older than 120 seconds."""
        cutoff = int(current_time) - 120
        keys_to_remove = [k for k in self._counts if k[2] < cutoff]
        for k in keys_to_remove:
            del self._counts[k]
        self._last_cleanup = current_time

    def reset(self) -> None:
        """Reset rate limiter counts state (used for test isolation)."""
        self._counts.clear()
        self._last_cleanup = time.time()


# Singleton limiter instance
_limiter = FixedWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware enforcing per-endpoint and per-role request limits.

    Emits standard rate limit response headers per house API standard:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    - Retry-After (on HTTP 429)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        method = request.method

        category = _get_endpoint_category(method, path)

        # Exclude health check from rate limiting
        if category == "health":
            return await call_next(request)

        identifier, role = _extract_identity(request)
        is_sync_endpoint = category == "sync"

        allowed, limit, remaining, reset_seconds = _limiter.check_and_increment(
            identifier=identifier,
            is_sync_endpoint=is_sync_endpoint,
            role=role,
            category=category,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=path,
                method=method,
                category=category,
                limit=limit,
                reset_seconds=reset_seconds,
                role=role,
            )
            envelope = ErrorEnvelope(
                error=ErrorBody(
                    code="RATE_LIMITED",
                    message=f"Rate limit of {limit} requests per minute exceeded for '{category}' endpoints. Please try again in {reset_seconds} seconds.",
                )
            )
            err_response = JSONResponse(
                status_code=429,
                content=envelope.model_dump(),
                headers={"Retry-After": str(reset_seconds)},
            )
            err_response.headers["X-RateLimit-Limit"] = str(limit)
            err_response.headers["X-RateLimit-Remaining"] = str(remaining)
            err_response.headers["X-RateLimit-Reset"] = str(reset_seconds)
            return err_response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
