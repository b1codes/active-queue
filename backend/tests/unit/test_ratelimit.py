from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware.ratelimit import RateLimitMiddleware


@pytest.mark.asyncio
async def test_rate_limit_middleware_headers() -> None:
    """RateLimitMiddleware attaches rate limit headers to responses."""

    async def homepage(request: object) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", homepage)])
    app.add_middleware(RateLimitMiddleware)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "99"
        assert response.headers["X-RateLimit-Reset"] == "3600"
