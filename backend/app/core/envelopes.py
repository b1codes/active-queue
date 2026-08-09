from __future__ import annotations

from typing import Literal, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    field: str
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []


class SuccessEnvelope[T](BaseModel):
    status: Literal["success"] = "success"
    data: T
    error: None = None


class ErrorEnvelope(BaseModel):
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
