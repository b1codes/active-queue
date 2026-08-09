from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# Keys that must ALWAYS be redacted by key name, regardless of call-site discipline
REDACT_KEYS = {
    "authorization",
    "id_token",
    "idtoken",
    "refresh_token",
    "refreshtoken",
    "access_token",
    "accesstoken",
    "token",
    "youtube_api_key",
    "api_key",
    "apikey",
    "secret",
    "client_secret",
    "password",
    "passwd",
    "credential",
    "credentials",
}


def redact_sensitive_keys(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Processor that redacts sensitive values by key name.

    Redacts ID tokens, refresh tokens, Authorization header values, YouTube API key,
    passwords, and credentials by key name so redaction does not depend on call-site discipline.
    Emails are redacted unless the record severity level is ERROR or CRITICAL.
    """
    log_level = str(event_dict.get("level", method_name)).lower()

    def redact_val(key: str, val: Any) -> Any:
        key_lower = key.lower()

        # Always redact matching key names
        if any(rk in key_lower for rk in REDACT_KEYS):
            return "[REDACTED]"

        # Redact email outside of ERROR/CRITICAL logs
        if "email" in key_lower and log_level not in ("error", "critical"):
            return "[REDACTED_EMAIL]"

        if isinstance(val, dict):
            return {k: redact_val(k, v) for k, v in val.items()}
        if isinstance(val, list):
            return [redact_val(key, item) for item in val]
        return val

    res = {k: redact_val(k, v) for k, v in event_dict.items()}
    return res


def map_house_fields(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Maps structlog fields to the house logging format.

    House fields: timestamp, level, component, message, latency_ms.
    Trace correlation: maps trace to logging.googleapis.com/trace for Cloud Logging.
    """
    if "logger_name" in event_dict and "component" not in event_dict:
        event_dict["component"] = event_dict.pop("logger_name")
    elif "component" not in event_dict:
        event_dict["component"] = "activequeue"

    if "event" in event_dict and "message" not in event_dict:
        event_dict["message"] = event_dict.pop("event")

    # Map trace to Cloud Logging trace field if trace is set
    if "trace" in event_dict and "logging.googleapis.com/trace" not in event_dict:
        event_dict["logging.googleapis.com/trace"] = event_dict["trace"]

    return event_dict


def configure_logging(debug: bool = False, log_level: str = "INFO") -> None:
    """Configures structlog and standard library logging with JSONRenderer.

    Outputs structured JSON to stdout with house fields and redaction processor.
    """
    level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        map_house_fields,
        redact_sensitive_keys,
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Quiet external noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
