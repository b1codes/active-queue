from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.envelopes import ErrorBody, ErrorEnvelope, SuccessEnvelope
from app.core.firestore import get_firestore_client

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check() -> JSONResponse:
    """Health check endpoint per SPEC §9.8.

    Reads a sentinel document from Firestore to verify connectivity.
    Returns 200 when Firestore is reachable, 503 otherwise.

    The provider check is non-critical — it reports status but NEVER fails
    the endpoint. Failing health during a YouTube outage would cause Cloud Run
    to cycle healthy instances, converting a partial degradation into a full one.
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

    # Provider check is non-critical — always reports, never fails the endpoint
    provider_status: dict[str, str] = {"status": "unknown"}

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
