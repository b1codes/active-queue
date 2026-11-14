from __future__ import annotations

from typing import Annotated, Any, Literal, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.core.errors import ERROR_CODES

T = TypeVar("T")


class ResponseSchema(BaseModel):
    """Base for every model serialized into a response body.

    Fields with defaults are always present on the wire (we never use exclude_unset /
    exclude_none), so the published contract marks them required: a consumer can rely
    on `content_id: null` being sent rather than the key being absent.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class RequestSchema(BaseModel):
    """Base for every request body model.

    Strict, so a value of the wrong JSON type is a 400 rather than coerced: lax mode
    turned `"sync_enabled": 0` or `"false"` into a boolean the client never sent. Integer
    fields take `JsonInt`.
    """

    model_config = ConfigDict(strict=True)


def _integral_float_to_int(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


# A JSON Schema `integer` includes 1800.0 (a number with no fractional part), which strict
# mode alone rejects. Strings, booleans and 1800.5 are still rejected.
JsonInt = Annotated[int, BeforeValidator(_integral_float_to_int)]

# Bounds go on the int, before the validator, or the contract gets raw `ge`/`le` keys
# instead of `minimum`/`maximum`.
DurationSeconds = Annotated[int, Field(ge=300, le=86400), BeforeValidator(_integral_float_to_int)]


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
