"""Browser-facing hardening (SPEC §2): the only client is the native app, so no origin is
ever granted cross-origin access, and FastAPI's debug mode stays off in every env."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.main import app

if TYPE_CHECKING:
    from httpx import AsyncClient

ORIGINS = ["https://evil.example.com", "null", "http://localhost:8081"]


@pytest.mark.parametrize("origin", ORIGINS)
async def test_preflight_grants_no_origin(client: AsyncClient, origin: str) -> None:
    resp = await client.options(
        "/api/v1/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
    assert "access-control-allow-credentials" not in resp.headers


@pytest.mark.parametrize("origin", ORIGINS)
async def test_simple_requests_grant_no_origin(client: AsyncClient, origin: str) -> None:
    resp = await client.get("/api/v1/activities", headers={"Origin": origin})
    assert "access-control-allow-origin" not in resp.headers


def test_fastapi_debug_mode_is_off() -> None:
    """debug=True would serve tracebacks in 500 responses."""
    assert app.debug is False
