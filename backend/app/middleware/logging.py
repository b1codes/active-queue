from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import settings
from app.core.errors import AppError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Binds request context to structlog and logs request lifecycle.

    Fields per SPEC §10.1: request_id, trace, uid, method, path, latency_ms.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        clear_contextvars()

        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        trace = request.headers.get("x-cloud-trace-context", "")

        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            component="router",
        )

        if trace:
            # Cloud Trace ID format: projects/{PROJECT_ID}/traces/{TRACE_ID}
            trace_id = trace.split("/")[0]
            bind_contextvars(trace=f"projects/{settings.gcp_project_id}/traces/{trace_id}")

        uid = getattr(request.state, "uid", None)
        if uid:
            bind_contextvars(uid=str(uid))

        logger.info("request_started")
        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except AppError:
            raise
        except Exception:
            logger.exception("request_unhandled_exception")
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        bind_contextvars(status_code=response.status_code, latency_ms=latency_ms)

        log_level = "warning" if response.status_code >= 400 else "info"
        getattr(logger, log_level)("request_finished")

        response.headers["x-request-id"] = request_id
        return response
