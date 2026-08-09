from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.envelopes import ErrorBody, ErrorDetail, ErrorEnvelope
from app.core.errors import AppError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException
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


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI RequestValidationError handler returning standard house error envelope."""
    details: list[ErrorDetail] = []
    for err in exc.errors():
        field_path = ".".join(str(loc) for loc in err.get("loc", []) if loc != "body")
        details.append(
            ErrorDetail(
                field=field_path or "body",
                issue=err.get("msg", "Invalid value"),
            )
        )

    envelope = ErrorEnvelope(
        error=ErrorBody(
            code="VALIDATION_FAILED",
            message="The request contains invalid input parameters.",
            details=details,
        )
    )
    return JSONResponse(status_code=400, content=envelope.model_dump())


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Starlette/FastAPI HTTPException handler returning standard house error envelope."""
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "AUTH_TOKEN_MISSING"
    elif exc.status_code == 403:
        code = "ACCOUNT_DISABLED"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 429:
        code = "RATE_LIMITED"

    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=str(exc.detail) if exc.detail else "An HTTP error occurred",
        )
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())
