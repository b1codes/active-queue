from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.envelopes import ErrorDetail


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class ValidationError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 400, details)


class AuthenticationError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 401, details)


class AuthorizationError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 403, details)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 404, details)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 409, details)


class RateLimitError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 429, details)


class ProviderError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 503, details)


class InternalError(AppError):
    def __init__(self, code: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(code, message, 500, details)


ERROR_CODES: dict[str, int] = {
    "VALIDATION_FAILED": 400,
    "AUTH_TOKEN_MISSING": 401,
    "AUTH_TOKEN_INVALID": 401,
    "AUTH_TOKEN_EXPIRED": 401,
    "ACCOUNT_DISABLED": 403,
    "SESSION_NOT_FOUND": 404,
    "CONTENT_NOT_FOUND": 404,
    "SOURCE_NOT_FOUND": 404,
    "SOURCE_URL_UNPARSEABLE": 422,
    "SOURCE_UNSUPPORTED": 422,
    "SOURCE_NOT_ACCESSIBLE": 404,
    "SOURCE_ALREADY_ADDED": 409,
    "ACTIVE_SESSION_EXISTS": 409,
    "SESSION_NOT_STARTED": 409,
    "SESSION_ALREADY_TERMINAL": 409,
    "DURATION_OUT_OF_RANGE": 422,
    "ACTIVITY_DURATION_MISMATCH": 422,
    "SOURCE_LIMIT_REACHED": 422,
    "RATE_LIMITED": 429,
    "FEATURE_NOT_AVAILABLE": 501,
    "PROVIDER_QUOTA_EXCEEDED": 503,
    "PROVIDER_UNAVAILABLE": 503,
    "INTERNAL_ERROR": 500,
}
