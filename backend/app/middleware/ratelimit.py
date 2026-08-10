from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.envelopes import ErrorBody, ErrorEnvelope

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Fixed window size in seconds
WINDOW_SECONDS = 60

# Rate limits per SPEC §14.4 & Subtask 3
LIMIT_GENERAL = 60  # 60 req/min general per user
LIMIT_SYNC = 10  # 10 req/min on sync trigger endpoints


class FixedWindowRateLimiter:
    """Instance-local fixed-window in-memory rate limiter per SPEC §14.4.

    Architectural Compromise Note (SPEC §14.4):
    v1 uses an instance-local fixed-window limiter, so rate limit headers are approximate per Cloud Run instance.
    An accurate distributed limiter would require Firestore or Redis writes per request, roughly doubling cost
    and latency to protect against a threat v1 does not face. Cloud Armor edge limiting is reserved for v1.1.
    """

    def __init__(self) -> None:
        # Key: (identifier, is_sync_endpoint, window_start_time) -> count
        self._counts: dict[tuple[str, bool, int], int] = {}
        self._last_cleanup = time.time()

    def check_and_increment(
        self, identifier: str, is_sync_endpoint: bool, now: float | None = None
    ) -> tuple[bool, int, int, int]:
        """Check and increment request count for identifier in current 60s window.

        Returns tuple of:
        (is_allowed: bool, limit: int, remaining: int, reset_seconds: int)
        """
        current_time = now if now is not None else time.time()
        window_start = int(current_time) // WINDOW_SECONDS * WINDOW_SECONDS
        reset_seconds = max(1, int(window_start + WINDOW_SECONDS - current_time))

        limit = LIMIT_SYNC if is_sync_endpoint else LIMIT_GENERAL
        key = (identifier, is_sync_endpoint, window_start)

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


# Singleton limiter instance
_limiter = FixedWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware enforcing 60 req/min general limit and 10 req/min sync trigger limit.

    Emits standard rate limit response headers per house API standard:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Exclude health check from rate limiting
        if path == "/healthz":
            return await call_next(request)

        # Identify user by authenticated UID (set by auth middleware) or client IP fallback
        user_id = getattr(request.state, "uid", None)
        if not user_id:
            client_ip = request.client.host if request.client else "anonymous"
            identifier = f"ip:{client_ip}"
        else:
            identifier = f"uid:{user_id}"

        # Detect sync trigger endpoint: POST /api/v1/sources/{source_id}/sync
        is_sync_endpoint = request.method == "POST" and path.endswith("/sync")

        allowed, limit, remaining, reset_seconds = _limiter.check_and_increment(
            identifier=identifier,
            is_sync_endpoint=is_sync_endpoint,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=path,
                limit=limit,
                reset_seconds=reset_seconds,
            )
            envelope = ErrorEnvelope(
                error=ErrorBody(
                    code="RATE_LIMITED",
                    message="Too many requests. Please try again later.",
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
