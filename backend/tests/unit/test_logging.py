from __future__ import annotations

from app.core.logging import map_house_fields, redact_sensitive_keys


def test_redact_sensitive_keys_by_key_name() -> None:
    """Redacts tokens, authorization header, passwords, and API keys by key name."""
    event_dict = {
        "event": "user_login",
        "authorization": "Bearer secret_token_123",
        "id_token": "eyJhbGciOi...",
        "refresh_token": "rt_123456",
        "youtube_api_key": "AIzaSyD...",
        "api_key": "key_999",
        "password": "super_secret_pass",
        "nested": {
            "secret": "hidden_value",
            "client_secret": "cs_123",
        },
        "safe_field": "visible_data",
    }

    result = redact_sensitive_keys(None, "info", event_dict)

    assert result["authorization"] == "[REDACTED]"
    assert result["id_token"] == "[REDACTED]"
    assert result["refresh_token"] == "[REDACTED]"
    assert result["youtube_api_key"] == "[REDACTED]"
    assert result["api_key"] == "[REDACTED]"
    assert result["password"] == "[REDACTED]"
    assert result["nested"]["secret"] == "[REDACTED]"
    assert result["nested"]["client_secret"] == "[REDACTED]"
    assert result["safe_field"] == "visible_data"


def test_redact_case_insensitive() -> None:
    """Redaction matches keys regardless of casing."""
    event_dict = {
        "Authorization": "Bearer token",
        "YouTube_API_Key": "AIza...",
        "PassWord": "123",
    }
    result = redact_sensitive_keys(None, "info", event_dict)
    assert result["Authorization"] == "[REDACTED]"
    assert result["YouTube_API_Key"] == "[REDACTED]"
    assert result["PassWord"] == "[REDACTED]"


def test_redact_email_by_severity_level() -> None:
    """Email is redacted for INFO logs but preserved for ERROR logs per SPEC §10.1."""
    info_dict = {"email": "user@example.com", "level": "info"}
    info_result = redact_sensitive_keys(None, "info", info_dict)
    assert info_result["email"] == "[REDACTED_EMAIL]"

    error_dict = {"email": "user@example.com", "level": "error"}
    error_result = redact_sensitive_keys(None, "error", error_dict)
    assert error_result["email"] == "user@example.com"


def test_map_house_fields() -> None:
    """map_house_fields maps event to message and logger_name to component."""
    event_dict = {"event": "request_finished", "logger_name": "app.router"}
    result = map_house_fields(None, "info", event_dict)
    assert result["message"] == "request_finished"
    assert result["component"] == "app.router"
