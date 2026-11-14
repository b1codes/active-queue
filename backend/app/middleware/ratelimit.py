from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.envelopes import ErrorBody, ErrorEnvelope
from app.core.errors import RateLimitError
from app.core.security import AuthenticatedUser, get_current_user

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
    if path in ("/health", "/healthz"):
        return "health"
    if method == "POST" and path.endswith("/sync"):
        return "sync"
    if (
        method in ("POST", "PUT", "DELETE") and ("/sources" in path or "/sessions" in path)
    ) or path.endswith("/match"):
        return "heavy"
    return "general"


def client_ip(request: Request) -> str:
    """The caller's IP, reading X-Forwarded-For only as far as trusted proxies vouch for it.

    With trusted_proxy_hops = N, the Nth entry from the right of X-Forwarded-For is the
    address our own edge saw. Anything further left was supplied by the client and is
    never trusted. 0 (local dev, tests) uses the TCP peer address.
    """
    hops = settings.trusted_proxy_hops
    if hops > 0:
        forwarded = request.headers.get("X-Forwarded-For", "")
        entries = [e.strip() for e in forwarded.split(",") if e.strip()]
        if len(entries) >= hops:
            return entries[-hops]
    return request.client.host if (request.client and request.client.host) else "unknown"


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
            if identifier.startswith(("uid:", "user")):
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


def _rate_limit_headers(limit: int, remaining: int, reset_seconds: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_seconds),
    }


async def enforce_user_rate_limit(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Per-user limits (SPEC §10.2), keyed by the uid of a *verified* token.

    Registered on every authenticated router, so it runs after get_current_user has
    verified the token. Keying on unverified claims would let anyone forge a token to
    dodge their own limit, or to burn another user's budget by naming their uid.
    v1 has a single role (SPEC §3.3), so every verified user gets the "user" tier.
    """
    category = _get_endpoint_category(request.method, request.url.path)
    allowed, limit, remaining, reset_seconds = _limiter.check_and_increment(
        identifier=f"uid:{user.uid}", role="user", category=category
    )
    request.state.rate_limit_headers = _rate_limit_headers(limit, remaining, reset_seconds)
    if not allowed:
        logger.warning(
            "rate_limit_exceeded",
            identifier=f"uid:{user.uid}",
            path=request.url.path,
            method=request.method,
            category=category,
            limit=limit,
            reset_seconds=reset_seconds,
        )
        raise RateLimitError(
            code="RATE_LIMITED",
            message=(
                f"Rate limit of {limit} requests per minute exceeded for '{category}' "
                f"endpoints. Please try again in {reset_seconds} seconds."
            ),
            headers={"Retry-After": str(reset_seconds)},
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP flood guard in front of everything except /health and /healthz.

    It never looks inside the Authorization header: the coarse per-IP budget
    (rate_limit_ip) caps what any one address can send, verified or not, before any token
    work happens. Per-user limits are enforced by enforce_user_rate_limit after
    verification, and their values are the X-RateLimit-* headers authenticated
    responses carry. Unauthenticated responses carry the per-IP values.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if _get_endpoint_category(request.method, path) == "health":
            return await call_next(request)

        ip = client_ip(request)
        allowed, limit, remaining, reset_seconds = _limiter.check_and_increment(
            identifier=f"ip:{ip}",
            role="anonymous",
            category="ip",
            custom_limit=settings.rate_limit_ip,
        )
        ip_headers = _rate_limit_headers(limit, remaining, reset_seconds)

        if not allowed:
            logger.warning(
                "ip_rate_limit_exceeded",
                identifier=f"ip:{ip}",
                path=path,
                method=request.method,
                limit=limit,
                reset_seconds=reset_seconds,
            )
            envelope = ErrorEnvelope(
                error=ErrorBody(
                    code="RATE_LIMITED",
                    message=(
                        f"Rate limit of {limit} requests per minute exceeded for this "
                        f"address. Please try again in {reset_seconds} seconds."
                    ),
                )
            )
            return JSONResponse(
                status_code=429,
                content=envelope.model_dump(),
                headers={"Retry-After": str(reset_seconds), **ip_headers},
            )

        response = await call_next(request)
        user_headers: dict[str, str] | None = getattr(request.state, "rate_limit_headers", None)
        response.headers.update(user_headers or ip_headers)
        return response
