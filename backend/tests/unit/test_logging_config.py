"""configure_logging end to end: what actually reaches stdout (SPEC §10.1)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
import structlog

from app.core.logging import configure_logging, map_house_fields, redact_sensitive_keys

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level
    structlog.reset_defaults()


def _json_lines(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def test_prod_emits_single_encoded_json_with_house_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(env="prod")
    structlog.get_logger("app.test").info(
        "thing_happened",
        trace="projects/p/traces/abc",
        id_token="eyJ.secret",
        email="person@example.com",
        latency_ms=1.5,
    )
    [line] = _json_lines(capsys.readouterr().out)
    assert line["message"] == "thing_happened"
    assert line["level"] == "info"
    assert line["component"] == "app.test"
    assert line["logging.googleapis.com/trace"] == "projects/p/traces/abc"
    assert line["id_token"] == "[REDACTED]"
    assert line["email"] == "[REDACTED_EMAIL]"
    assert line["latency_ms"] == 1.5
    assert "timestamp" in line
    assert not any(k.startswith("_") for k in line)  # processor meta stripped


def test_stdlib_loggers_are_rendered_and_redacted_too(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(env="staging")
    logging.getLogger("thirdparty").warning("plain stdlib message")
    [line] = _json_lines(capsys.readouterr().out)
    assert line["message"] == "plain stdlib message"
    assert line["level"] == "warning"


def test_errors_keep_email_for_support(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(env="prod")
    structlog.get_logger("app.test").error("boom", email="person@example.com")
    [line] = _json_lines(capsys.readouterr().out)
    assert line["email"] == "person@example.com"


def test_local_uses_console_renderer_and_levels(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(env="local", log_level="warning")
    log = structlog.get_logger("app.test")
    log.info("hidden_info")
    log.warning("shown_warning")
    out = capsys.readouterr().out
    assert "shown_warning" in out
    assert "hidden_info" not in out
    assert not _json_lines(out)
    assert logging.getLogger().level == logging.WARNING


def test_debug_flag_forces_debug_level() -> None:
    configure_logging(debug=True, log_level="ERROR", env="prod")
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("google.cloud").level == logging.WARNING


def test_redaction_recurses_into_lists_of_dicts() -> None:
    out = redact_sensitive_keys(
        None, "info", {"items": [{"password": "p", "ok": 1}, "plain"], "level": "info"}
    )
    assert out["items"] == [{"password": "[REDACTED]", "ok": 1}, "plain"]


def test_map_house_fields_preserves_explicit_component_and_trace() -> None:
    out = map_house_fields(
        None,
        "info",
        {
            "event": "e",
            "component": "router",
            "logger_name": "x",
            "trace": "t",
            "logging.googleapis.com/trace": "already",
        },
    )
    assert out["component"] == "router"
    assert out["logging.googleapis.com/trace"] == "already"
    assert map_house_fields(None, "info", {"event": "e"})["component"] == "activequeue"
