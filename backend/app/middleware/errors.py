from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.envelopes import ErrorBody, ErrorEnvelope
from app.core.errors import AppError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

logger = structlog.get_logger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catches AppError exceptions and converts them to the house error envelope.

    Generic exceptions are caught and returned as INTERNAL_ERROR (500).
    INTERNAL_ERROR must NEVER leak exception messages or stack traces to the client.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except AppError as exc:
            logger.warning(
                "app_error",
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
            )
            envelope = ErrorEnvelope(
                error=ErrorBody(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                )
            )
            return JSONResponse(
                status_code=exc.status_code,
                content=envelope.model_dump(),
            )
        except Exception:
            # Log full exception internally but NEVER expose to client
            logger.error("internal_error", exc_info=True)
            envelope = ErrorEnvelope(
                error=ErrorBody(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred.",
                )
            )
            return JSONResponse(status_code=500, content=envelope.model_dump())
