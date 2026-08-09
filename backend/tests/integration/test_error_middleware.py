from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import APIRouter, Query
from starlette.exceptions import HTTPException

from app.core.errors import NotFoundError
from app.main import app

if TYPE_CHECKING:
    from httpx import AsyncClient

dummy_router = APIRouter(prefix="/test-errors")


@dummy_router.get("/app-error")
async def trigger_app_error() -> None:
    raise NotFoundError(code="SESSION_NOT_FOUND", message="Session does not exist")


@dummy_router.get("/internal-error")
async def trigger_internal_error() -> None:
    # Secret message / exception details
    raise RuntimeError("Secret DB Password exposed in raw stack trace")


@dummy_router.get("/validation-error")
async def trigger_validation_error(num: int = Query(..., ge=1, le=10)) -> dict[str, int]:
    return {"num": num}


@dummy_router.get("/http-error")
async def trigger_http_error() -> None:
    raise HTTPException(status_code=401, detail="Unauthorized token missing")


app.include_router(dummy_router)


@pytest.mark.asyncio
async def test_app_error_middleware(client: AsyncClient) -> None:
    """AppError exceptions are mapped to the house error envelope."""
    response = await client.get("/test-errors/app-error")
    assert response.status_code == 404

    data = response.json()
    assert data["status"] == "error"
    assert data["data"] is None
    assert data["error"]["code"] == "SESSION_NOT_FOUND"
    assert data["error"]["message"] == "Session does not exist"


@pytest.mark.asyncio
async def test_internal_error_does_not_leak_details(client: AsyncClient) -> None:
    """INTERNAL_ERROR must never leak exception messages or stack traces."""
    response = await client.get("/test-errors/internal-error")
    assert response.status_code == 500

    data = response.json()
    assert data["status"] == "error"
    assert data["data"] is None
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert data["error"]["message"] == "An unexpected error occurred."
    assert "Secret DB Password" not in response.text


@pytest.mark.asyncio
async def test_validation_error_handler_envelope(client: AsyncClient) -> None:
    """FastAPI validation errors return house VALIDATION_FAILED error envelope."""
    response = await client.get("/test-errors/validation-error?num=100")
    assert response.status_code == 400

    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "VALIDATION_FAILED"
    assert len(data["error"]["details"]) > 0


@pytest.mark.asyncio
async def test_http_exception_handler_envelope(client: AsyncClient) -> None:
    """FastAPI HTTPException returns house error envelope."""
    response = await client.get("/test-errors/http-error")
    assert response.status_code == 401

    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "AUTH_TOKEN_MISSING"
