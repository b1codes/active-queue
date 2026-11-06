"""App wiring that the feature suites don't reach: handlers, middleware, lifespan, factory."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException
from starlette.requests import Request  # noqa: TC002 - FastAPI resolves it at runtime

from app.core.config import Settings
from app.core.sanitizer import (
    is_valid_document_id,
    sanitize_document_id,
    sanitize_identifier,
    sanitize_string_list,
    sanitize_text,
    sanitize_url,
)
from app.middleware.errors import ErrorHandlingMiddleware, http_exception_handler
from app.middleware.logging import RequestLoggingMiddleware
from app.providers.factory import get_provider
from app.providers.fixture import FixtureProvider
from app.providers.youtube import YouTubeProvider


def _app_raising(exc: Exception) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/boom")
    async def boom(request: Request) -> None:
        request.state.uid = "uid-from-auth"
        raise exc

    @app.get("/ok")
    async def ok(request: Request) -> dict[str, str]:
        request.state.uid = "uid-from-auth"
        return {"ok": "yes"}

    return app


async def _get(app: FastAPI, path: str, **headers: str) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        return await c.get(path, headers=headers)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "AUTH_TOKEN_MISSING"),
        (403, "ACCOUNT_DISABLED"),
        (404, "NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (405, "HTTP_ERROR"),
    ],
)
async def test_http_exceptions_use_the_error_envelope(status: int, code: str) -> None:
    resp = await _get(_app_raising(HTTPException(status_code=status, detail="d")), "/boom")
    assert resp.status_code == status
    body = resp.json()
    assert body == {
        "status": "error",
        "data": None,
        "error": {"code": code, "message": "d", "details": []},
    }


async def test_http_exception_without_detail_has_generic_message() -> None:
    resp = await _get(_app_raising(HTTPException(status_code=418, detail="")), "/boom")
    assert resp.json()["error"]["message"] == "An HTTP error occurred"


async def test_unhandled_exception_never_leaks_its_message() -> None:
    resp = await _get(_app_raising(RuntimeError("db password is hunter2")), "/boom")
    assert resp.status_code == 500
    assert "hunter2" not in resp.text
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


async def test_unknown_route_404_uses_envelope() -> None:
    from app.main import app

    resp = await _get(app, "/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_request_log_binds_request_id_trace_and_uid() -> None:
    bound: dict[str, Any] = {}

    def capture(**kw: Any) -> None:
        bound.update(kw)

    with patch("app.middleware.logging.bind_contextvars", side_effect=capture):
        resp = await _get(
            _app_raising(RuntimeError()),
            "/ok",
            **{"x-request-id": "req-1", "x-cloud-trace-context": "abc123/456;o=1"},
        )
    assert resp.headers["x-request-id"] == "req-1"
    assert bound["request_id"] == "req-1"
    assert bound["trace"].endswith("/traces/abc123")
    assert bound["uid"] == "uid-from-auth"  # set by auth during the request
    assert bound["status_code"] == 200


async def test_request_log_generates_request_id() -> None:
    resp = await _get(_app_raising(RuntimeError()), "/ok")
    assert len(resp.headers["x-request-id"]) == 36


async def test_lifespan_initialises_and_closes_dependencies() -> None:
    from app import main

    with (
        patch.object(main, "configure_logging") as cfg,
        patch.object(main, "init_firestore", AsyncMock()) as init_fs,
        patch.object(main, "init_firebase_admin") as init_fb,
        patch.object(main, "close_firestore", AsyncMock()) as close_fs,
    ):
        async with main.lifespan(main.app):
            cfg.assert_called_once()
            init_fs.assert_awaited_once()
            init_fb.assert_called_once()
            close_fs.assert_not_awaited()
        close_fs.assert_awaited_once()


def test_init_firebase_admin_initialises_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import security

    fake = MagicMock()
    fake.get_app.side_effect = ValueError("no app")
    monkeypatch.setattr(security, "firebase_admin", fake)
    security.init_firebase_admin(Settings(firebase_auth_emulator_host=None))
    fake.initialize_app.assert_called_once()

    fake.get_app.side_effect = None
    fake.initialize_app.reset_mock()
    security.init_firebase_admin(Settings(firebase_auth_emulator_host=None))
    fake.initialize_app.assert_not_called()


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("fixture", FixtureProvider),
        ("FIXTURE", FixtureProvider),
        ("youtube", YouTubeProvider),
        ("something-else", FixtureProvider),
    ],
)
def test_provider_factory(name: str, cls: type) -> None:
    assert isinstance(get_provider(name), cls)


def test_provider_factory_defaults_to_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.factory.settings.content_provider", "youtube")
    assert isinstance(get_provider(), YouTubeProvider)


# --------------------------------------------------------------------------- sanitizer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("   ", ""),
        ("<b>bold</b> text", "bold text"),
        ("<script>alert(1)</script>hello", "hello"),
        ("javascript:alert(1)", "alert(1)"),
        ("a\x00b\x07c", "abc"),
        ("x" * 20, "x" * 10),
    ],
)
def test_sanitize_text(raw: str | None, expected: str | None) -> None:
    assert sanitize_text(raw, max_length=10) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("  ", None),
        ("https://example.com/a?b=c", "https://example.com/a?b=c"),
        ("http://example.com", "http://example.com"),
        ("ftp://example.com", None),
        ("javascript:alert(1)", None),
        ("data:text/html,hi", None),
        ("https://e.com/" + "a" * 3000, None),
        ("no-scheme.example.com/path", "no-scheme.example.com/path"),
    ],
)
def test_sanitize_url(raw: str | None, expected: str | None) -> None:
    assert sanitize_url(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("  ", None),
        ("../../etc/passwd", "etc/passwd"),
        ("ok\x00id", "okid"),
        ("y" * 300, "y" * 200),
    ],
)
def test_sanitize_identifier(raw: str | None, expected: str | None) -> None:
    assert sanitize_identifier(raw) == expected


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("yt:dQw4w9WgXcQ", True),
        ("fx:fx_vid_0001", True),
        ("s_abc-123.x", True),
        ("a/b", False),
        (".", False),
        ("..", False),
        ("__x__", False),
        ("__", True),  # shorter than the reserved __.*__ form
        ("_x_", True),
        ("has space", False),
        ("", False),
    ],
)
def test_is_valid_document_id(value: str, ok: bool) -> None:
    assert is_valid_document_id(value) is ok


def test_sanitize_document_id() -> None:
    assert sanitize_document_id(None) is None
    assert sanitize_document_id("  ") is None
    assert sanitize_document_id(" yt:abc ") == "yt:abc"
    with pytest.raises(ValueError, match="letters, digits"):
        sanitize_document_id("bad/id")


def test_sanitize_string_list() -> None:
    assert sanitize_string_list(None) == []
    assert sanitize_string_list([" a ", "", "<i></i>", "b"]) == ["a", "b"]
    assert sanitize_string_list(["x"] * 10, max_items=3) == ["x", "x", "x"]


async def test_request_log_records_exceptions_escaping_inner_middleware() -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("escaped")

    with patch("app.middleware.logging.logger") as log, pytest.raises(RuntimeError):
        await _get(app, "/explode")
    log.exception.assert_called_once_with("request_unhandled_exception")
