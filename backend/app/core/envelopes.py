from __future__ import annotations

from typing import Any, Literal, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.core.errors import ERROR_CODES

T = TypeVar("T")


class ResponseSchema(BaseModel):
    """Base for every model serialized into a response body.

    Fields with defaults are always present on the wire (we never use exclude_unset /
    exclude_none), so the published contract marks them required: a consumer can rely
    on `content_id: null` being sent rather than the key being absent.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ErrorDetail(ResponseSchema):
    field: str
    issue: str


class ErrorBody(ResponseSchema):
    code: str
    message: str
    details: list[ErrorDetail] = []


class SuccessEnvelope[T](ResponseSchema):
    status: Literal["success"] = "success"
    data: T
    error: None = None


class ErrorEnvelope(ResponseSchema):
    status: Literal["error"] = "error"
    data: None = None
    error: ErrorBody


def success_response[T](data: T) -> SuccessEnvelope[T]:
    return SuccessEnvelope(data=data)


def error_response(
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


def _error_responses() -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` documenting the error envelope for every status in ERROR_CODES.

    Declaring 400/422 here also stops FastAPI from advertising its default 422
    HTTPValidationError body, which this API never returns (validation errors are
    re-shaped into a 400 ErrorEnvelope by middleware/errors.py).
    """
    by_status: dict[int, list[str]] = {}
    for code, status in sorted(ERROR_CODES.items()):
        by_status.setdefault(status, []).append(code)
    return {
        status: {
            "model": ErrorEnvelope,
            "description": "Error envelope. `error.code` is one of: " + ", ".join(codes),
        }
        for status, codes in sorted(by_status.items())
    }


ERROR_RESPONSES = _error_responses()
