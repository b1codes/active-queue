from __future__ import annotations

import logging
from typing import Any

import structlog


def redact_sensitive_keys(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """
    Custom processor that redact sensitive keys from log payload.
    """
    sensitive_substrings = [
        "id_token",
        "refresh_token",
        "authorization",
        "api_key",
        "youtube_api_key",
        "token",
        "secret",
        "password",
        "credential",
    ]

    def redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]"
                if any(s in str(k).lower() for s in sensitive_substrings)
                else redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [redact(item) for item in obj]
        return obj

    res = redact(event_dict)
    assert isinstance(res, dict)
    return res


def configure_logging(debug: bool = False, log_level: str = "INFO") -> None:
    level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=None, level=level)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_keys,
    ]

    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
