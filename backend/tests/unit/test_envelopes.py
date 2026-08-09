from __future__ import annotations

from app.core.envelopes import (
    ErrorBody,
    ErrorDetail,
    ErrorEnvelope,
    SuccessEnvelope,
    error_response,
    success_response,
)


def test_success_response_shape() -> None:
    """success_response creates the correct envelope structure."""
    envelope = success_response({"key": "value"})
    assert isinstance(envelope, SuccessEnvelope)

    dumped = envelope.model_dump()
    assert dumped["status"] == "success"
    assert dumped["data"] == {"key": "value"}
    assert dumped["error"] is None


def test_error_response_returns_json_response() -> None:
    """error_response creates a JSONResponse with the correct envelope."""
    resp = error_response(
        code="VALIDATION_FAILED",
        message="Invalid input",
        status_code=400,
    )
    assert resp.status_code == 400

    import json

    body = json.loads(resp.body.decode())
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_FAILED"
    assert body["error"]["message"] == "Invalid input"
    assert body["error"]["details"] == []


def test_error_response_with_details() -> None:
    """error_response includes field-level details when provided."""
    details = [ErrorDetail(field="email", issue="must be a valid email")]
    resp = error_response(
        code="VALIDATION_FAILED",
        message="Invalid input",
        details=details,
        status_code=400,
    )

    import json

    body = json.loads(resp.body.decode())
    assert len(body["error"]["details"]) == 1
    assert body["error"]["details"][0]["field"] == "email"


def test_error_envelope_model() -> None:
    """ErrorEnvelope can be constructed directly."""
    envelope = ErrorEnvelope(error=ErrorBody(code="TEST_CODE", message="Test message"))
    dumped = envelope.model_dump()
    assert dumped["status"] == "error"
    assert dumped["data"] is None
    assert dumped["error"]["code"] == "TEST_CODE"
