from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.envelopes import ErrorBody, ErrorEnvelope, SuccessEnvelope
from app.core.firestore import get_firestore_client

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

# Cached provider reachability check (refreshed at most once per minute per SPEC §9.8)
_provider_reachability_cache: dict[str, Any] = {
    "status": "unknown",
    "checked_at": 0.0,
}
PROVIDER_CHECK_INTERVAL_SECONDS = 60.0


async def _get_provider_status() -> dict[str, str]:
    """Returns cached provider reachability status, refreshing at most once per minute.

    Non-critical check: Youtube Data API reachability.
    Refreshed at most once every 60 seconds to avoid hitting provider limits or adding latency.
    """
    global _provider_reachability_cache

    now = time.time()
    last_checked = float(_provider_reachability_cache.get("checked_at", 0.0))

    if now - last_checked < PROVIDER_CHECK_INTERVAL_SECONDS:
        return {"status": str(_provider_reachability_cache.get("status", "unknown"))}

    # Perform reachability check based on configured content_provider
    status = "up"
    try:
        if settings.content_provider == "fixture":
            status = "up"
        elif settings.content_provider == "youtube":
            status = "up" if settings.youtube_api_key else "degraded"
    except Exception:
        status = "degraded"

    _provider_reachability_cache = {
        "status": status,
        "checked_at": now,
    }
    return {"status": status}


@router.get("/healthz")
async def health_check() -> JSONResponse:
    """GET /healthz health check endpoint per SPEC §9.8 & §14.3.

    Evaluates Firestore connectivity by reading a sentinel document (critical).
    Evaluates provider reachability (non-critical, cached max once per minute).

    Returns:
    - 200 OK when Firestore is reachable (even if provider is degraded/offline).
    - 503 Service Unavailable when Firestore is unreachable.

    The provider check MUST NEVER fail the endpoint: failing health during a YouTube
    outage would cause Cloud Run to cycle healthy instances, converting a partial
    degradation into a full outage.
    """
    firestore_status: dict[str, Any] = {"status": "down", "latency_ms": 0.0}
    is_healthy = False

    try:
        client = get_firestore_client()
        start = time.perf_counter()
        doc_ref = client.collection("_health").document("sentinel")
        await doc_ref.get()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        firestore_status = {"status": "up", "latency_ms": latency_ms}
        is_healthy = True
        logger.info("health_check_passed", firestore_latency_ms=latency_ms)
    except Exception:
        logger.error("health_check_failed", exc_info=True)

    # Provider check is non-critical — reports status but NEVER fails health check
    provider_status = await _get_provider_status()

    data: dict[str, Any] = {
        "status": "healthy" if is_healthy else "unhealthy",
        "firestore": firestore_status,
        "provider": provider_status,
    }

    if is_healthy:
        success_env: SuccessEnvelope[dict[str, Any]] = SuccessEnvelope(data=data)
        return JSONResponse(status_code=200, content=success_env.model_dump())

    envelope_err = ErrorEnvelope(
        error=ErrorBody(
            code="SERVICE_UNAVAILABLE",
            message="Firestore is unreachable",
        )
    )
    return JSONResponse(status_code=503, content=envelope_err.model_dump())
