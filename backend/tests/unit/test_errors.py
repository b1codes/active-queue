from __future__ import annotations

from app.core.errors import (
    ERROR_CODES,
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InternalError,
    NotFoundError,
    ProviderError,
    RateLimitError,
    ValidationError,
)


def test_app_error_is_exception() -> None:
    """AppError is a proper Exception subclass."""
    err = AppError(code="TEST_CODE", message="Test message", status_code=400)
    assert isinstance(err, Exception)
    assert err.code == "TEST_CODE"
    assert err.message == "Test message"
    assert err.status_code == 400
    assert err.details == []


def test_app_error_with_details() -> None:
    """AppError carries field-level error details."""
    from app.core.envelopes import ErrorDetail

    details = [ErrorDetail(field="name", issue="required")]
    err = AppError(
        code="VALIDATION_FAILED",
        message="Invalid",
        status_code=400,
        details=details,
    )
    assert len(err.details) == 1
    assert err.details[0].field == "name"


def test_error_subclass_status_codes() -> None:
    """Each error subclass sets the correct default HTTP status code."""
    assert ValidationError(code="V", message="m").status_code == 400
    assert AuthenticationError(code="A", message="m").status_code == 401
    assert AuthorizationError(code="Z", message="m").status_code == 403
    assert NotFoundError(code="N", message="m").status_code == 404
    assert ConflictError(code="C", message="m").status_code == 409
    assert RateLimitError(code="R", message="m").status_code == 429
    assert ProviderError(code="P", message="m").status_code == 503
    assert InternalError(code="I", message="m").status_code == 500


def test_error_codes_registry_completeness() -> None:
    """The error code registry contains all SPEC §9.7 codes."""
    expected_codes = {
        "VALIDATION_FAILED",
        "AUTH_TOKEN_MISSING",
        "AUTH_TOKEN_INVALID",
        "AUTH_TOKEN_EXPIRED",
        "ACCOUNT_DISABLED",
        "SESSION_NOT_FOUND",
        "CONTENT_NOT_FOUND",
        "SOURCE_NOT_FOUND",
        "SOURCE_URL_UNPARSEABLE",
        "SOURCE_UNSUPPORTED",
        "SOURCE_NOT_ACCESSIBLE",
        "SOURCE_ALREADY_ADDED",
        "ACTIVE_SESSION_EXISTS",
        "SESSION_NOT_STARTED",
        "SESSION_ALREADY_TERMINAL",
        "DURATION_OUT_OF_RANGE",
        "ACTIVITY_DURATION_MISMATCH",
        "SOURCE_LIMIT_REACHED",
        "RATE_LIMITED",
        "FEATURE_NOT_AVAILABLE",
        "PROVIDER_QUOTA_EXCEEDED",
        "PROVIDER_UNAVAILABLE",
        "INTERNAL_ERROR",
    }
    assert set(ERROR_CODES.keys()) == expected_codes


def test_internal_error_hierarchy() -> None:
    """InternalError is an AppError with 500 status."""
    err = InternalError(code="INTERNAL_ERROR", message="Something broke")
    assert isinstance(err, AppError)
    assert err.status_code == 500
