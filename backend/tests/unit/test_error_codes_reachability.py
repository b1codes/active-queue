from __future__ import annotations

from app.core.errors import (
    ERROR_CODES,
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InternalError,
    NotFoundError,
    NotImplementedAppError,
    ProviderError,
    RateLimitError,
    UnprocessableEntityError,
    ValidationError,
)


def test_all_spec_97_error_codes_registered() -> None:
    """Verify all 23 SPEC §9.7 error codes are registered with HTTP status mapping."""
    expected_codes = {
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

    for code, status in expected_codes.items():
        assert code in ERROR_CODES, f"Error code {code} missing from ERROR_CODES"
        assert ERROR_CODES[code] == status, f"Mismatch status for {code}"


def test_app_error_hierarchy_instantiation() -> None:
    """Verify every AppError subclass instantiates with expected HTTP status code."""
    errors: list[AppError] = [
        ValidationError("VALIDATION_FAILED", "Invalid input"),
        AuthenticationError("AUTH_TOKEN_INVALID", "Invalid token"),
        AuthorizationError("ACCOUNT_DISABLED", "Disabled"),
        NotFoundError("SESSION_NOT_FOUND", "Not found"),
        ConflictError("ACTIVE_SESSION_EXISTS", "Conflict"),
        RateLimitError("RATE_LIMITED", "Too many requests"),
        ProviderError("PROVIDER_QUOTA_EXCEEDED", "Quota exceeded"),
        UnprocessableEntityError("SOURCE_UNSUPPORTED", "Unsupported"),
        NotImplementedAppError("FEATURE_NOT_AVAILABLE", "Not implemented"),
        InternalError("INTERNAL_ERROR", "Internal error"),
    ]

    for err in errors:
        assert isinstance(err, AppError)
        assert err.status_code == ERROR_CODES[err.code]
