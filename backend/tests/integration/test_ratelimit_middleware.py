"""Rate limiting (SPEC §10.2): per-user limits on verified uids, plus a per-IP flood guard.

The threat model: the limiter must not be steerable by anything a caller can forge. A
token's claims are only trusted after firebase_admin has verified it, so a forged token can
neither dodge its sender's limit nor spend someone else's.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from firebase_admin import auth
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.core.config import settings
from app.main import app
from app.middleware.ratelimit import client_ip

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

ROUTE = "/api/v1/activities"


def _forged(**claims: Any) -> str:
    """An unsigned JWT with arbitrary claims, which the old limiter decoded and trusted."""

    def b64(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64(claims)}."


def _verifier(valid: dict[str, str]) -> Callable[..., dict[str, Any]]:
    """verify_id_token stand-in: tokens in `valid` map to their uid, anything else is bad."""

    def _verify(token: str, **_kwargs: Any) -> dict[str, Any]:
        if token not in valid:
            raise auth.InvalidIdTokenError("bad signature")
        return {"uid": valid[token], "sub": valid[token], "iat": 0}

    return _verify


@pytest.fixture
async def api() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_authenticated_responses_carry_the_per_user_budget(api: AsyncClient) -> None:
    with patch("firebase_admin.auth.verify_id_token", _verifier({"alice-token": "alice"})):
        resp = await api.get(ROUTE, headers=_bearer("alice-token"))

    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit"] == "60"
    assert resp.headers["X-RateLimit-Remaining"] == "59"
    assert int(resp.headers["X-RateLimit-Reset"]) >= 1


@pytest.mark.parametrize("path", ["/health", "/healthz"])
async def test_health_endpoint_bypasses_rate_limit(
    api: AsyncClient, mock_firestore_client: MagicMock, path: str
) -> None:
    resp = await api.get(path)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers


async def test_exceeding_the_user_limit_returns_a_graceful_429(api: AsyncClient) -> None:
    with patch("firebase_admin.auth.verify_id_token", _verifier({"alice-token": "alice"})):
        for _ in range(60):
            assert (await api.get(ROUTE, headers=_bearer("alice-token"))).status_code == 200
        resp = await api.get(ROUTE, headers=_bearer("alice-token"))

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-RateLimit-Limit"] == "60"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Rate limit of 60 requests per minute exceeded" in body["error"]["message"]


async def test_forged_tokens_naming_a_victim_do_not_spend_the_victims_budget(
    api: AsyncClient,
) -> None:
    """Regression: the limiter used to key on the unverified uid claim."""
    forged = _forged(uid="victim", user_id="victim", sub="victim")
    with patch("firebase_admin.auth.verify_id_token", _verifier({"victim-token": "victim"})):
        for _ in range(70):
            assert (await api.get(ROUTE, headers=_bearer(forged))).status_code == 401
        resp = await api.get(ROUTE, headers=_bearer("victim-token"))

    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Remaining"] == "59"


async def test_forged_role_claim_does_not_raise_the_limit(api: AsyncClient) -> None:
    """Regression: an unverified role="admin" claim used to triple the sender's limit."""
    token = _forged(uid="mallory", sub="mallory", role="admin")
    with patch("firebase_admin.auth.verify_id_token", _verifier({token: "mallory"})):
        resp = await api.get(ROUTE, headers=_bearer(token))

    assert resp.headers["X-RateLimit-Limit"] == "60"


async def test_rotating_forged_identities_from_one_ip_hits_the_ip_guard(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a fresh forged uid per request used to mint a fresh budget each time."""
    monkeypatch.setattr(settings, "rate_limit_ip", 5)
    with patch("firebase_admin.auth.verify_id_token", _verifier({})):
        statuses = [
            (await api.get(ROUTE, headers=_bearer(_forged(uid=f"u{i}", sub=f"u{i}")))).status_code
            for i in range(7)
        ]

    assert statuses == [401] * 5 + [429] * 2


async def test_ip_guard_429_is_well_formed(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_ip", 1)
    await api.get(ROUTE)
    resp = await api.get(ROUTE)

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-RateLimit-Limit"] == "1"
    assert resp.headers["X-RateLimit-Remaining"] == "0"


async def test_users_have_independent_budgets(api: AsyncClient) -> None:
    tokens = {"alice-token": "alice", "bob-token": "bob"}
    with patch("firebase_admin.auth.verify_id_token", _verifier(tokens)):
        for _ in range(60):
            await api.get(ROUTE, headers=_bearer("alice-token"))
        alice = await api.get(ROUTE, headers=_bearer("alice-token"))
        bob = await api.get(ROUTE, headers=_bearer("bob-token"))

    assert alice.status_code == 429
    assert bob.status_code == 200


async def test_sync_has_its_own_tighter_budget(
    api: AsyncClient, mock_firestore_client: MagicMock
) -> None:
    """10/min on POST /sources/{id}/sync is enforced before the handler touches Firestore."""
    # The admitted requests 404 on a missing source. A mock snapshot "exists", fails Source
    # validation, and rendering each 500's traceback took ~3s, so the requests straddled a
    # fixed-window boundary often enough to flake.
    snapshot = mock_firestore_client.collection.return_value.document.return_value.get
    snapshot.return_value.exists = False
    with patch("firebase_admin.auth.verify_id_token", _verifier({"alice-token": "alice"})):
        first = await api.post("/api/v1/sources/src_1/sync", headers=_bearer("alice-token"))
        for _ in range(9):
            await api.post("/api/v1/sources/src_1/sync", headers=_bearer("alice-token"))
        limited = await api.post("/api/v1/sources/src_1/sync", headers=_bearer("alice-token"))
        general = await api.get(ROUTE, headers=_bearer("alice-token"))

    assert first.headers["X-RateLimit-Limit"] == "10"
    assert limited.status_code == 429
    assert general.status_code == 200
    assert general.headers["X-RateLimit-Remaining"] == "59"


async def test_concurrent_burst_admits_exactly_the_limit(api: AsyncClient) -> None:
    with patch("firebase_admin.auth.verify_id_token", _verifier({"alice-token": "alice"})):
        results = await asyncio.gather(
            *(api.get(ROUTE, headers=_bearer("alice-token")) for _ in range(80))
        )

    statuses = sorted(r.status_code for r in results)
    assert statuses.count(200) == 60
    assert statuses.count(429) == 20


# ---------------------------------------------------------------------------
# Client IP resolution behind proxies
# ---------------------------------------------------------------------------


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.mark.parametrize(
    ("hops", "forwarded", "expected"),
    [
        pytest.param(0, "203.0.113.9", "10.0.0.1", id="no-proxy-ignores-header"),
        pytest.param(1, "203.0.113.9", "203.0.113.9", id="one-proxy"),
        pytest.param(1, "6.6.6.6, 203.0.113.9", "203.0.113.9", id="spoofed-prefix-ignored"),
        pytest.param(2, "6.6.6.6, 203.0.113.9, 10.1.1.1", "203.0.113.9", id="two-proxies"),
        pytest.param(2, "203.0.113.9", "10.0.0.1", id="short-header-falls-back-to-peer"),
        pytest.param(1, None, "10.0.0.1", id="missing-header-falls-back-to-peer"),
    ],
)
def test_client_ip_trusts_only_the_configured_proxy_hops(
    monkeypatch: pytest.MonkeyPatch, hops: int, forwarded: str | None, expected: str
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", hops)
    assert client_ip(_request("10.0.0.1", forwarded)) == expected
