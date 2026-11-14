"""Request bodies are strict about JSON types and publish the ID rule they enforce.

Found by Schemathesis (tests/emulator/test_schemathesis_emulator.py): lax mode coerced
`"sync_enabled": 0` to False, and the contract didn't state the ID rule the API enforced,
so schema-valid IDs from a contract-driven client got 400s.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.core.sanitizer import DOCUMENT_ID_PATTERN
from app.features.content.schemas import ContentMatchRequest, TimeMatchRequest
from app.features.sessions.schemas import CreateSessionRequest
from app.features.users.schemas import UpdatePreferencesRequest

SESSION = {"activity_id": "running", "match_mode": "time_first"}


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (UpdatePreferencesRequest, {"sync_enabled": 0}),
        (UpdatePreferencesRequest, {"dark_mode": "false"}),
        (UpdatePreferencesRequest, {"default_time_block_seconds": "1800"}),
        (UpdatePreferencesRequest, {"default_time_block_seconds": True}),
        (UpdatePreferencesRequest, {"default_time_block_seconds": 1800.5}),
        (TimeMatchRequest, {"target_duration_seconds": "1800"}),
        (CreateSessionRequest, {**SESSION, "target_duration_seconds": "1800"}),
        (ContentMatchRequest, {"content_id": 123}),
    ],
)
def test_wrong_json_types_are_rejected_not_coerced(
    model: type[BaseModel], body: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(body))


@pytest.mark.parametrize(
    ("model", "body", "field", "expected"),
    [
        (
            UpdatePreferencesRequest,
            {"default_time_block_seconds": 1800.0},
            "default_time_block_seconds",
            1800,
        ),
        (TimeMatchRequest, {"target_duration_seconds": 1800.0}, "target_duration_seconds", 1800),
        (
            CreateSessionRequest,
            {**SESSION, "target_duration_seconds": 600.0},
            "target_duration_seconds",
            600,
        ),
    ],
)
def test_integral_floats_are_json_schema_integers(
    model: type[BaseModel], body: dict[str, Any], field: str, expected: int
) -> None:
    parsed = model.model_validate_json(json.dumps(body))
    value = getattr(parsed, field)
    assert value == expected
    assert type(value) is int


@pytest.mark.parametrize("content_id", [" yt:abc ", "yt:abc\n", "../yt:abc", "__x__", "."])
def test_ids_are_rejected_not_rewritten(content_id: str) -> None:
    """The old sanitizer rewrote " yt:abc " to "yt:abc"; an ID the API never issued is wrong."""
    with pytest.raises(ValidationError):
        ContentMatchRequest(content_id=content_id)
    with pytest.raises(ValidationError):
        CreateSessionRequest.model_validate({**SESSION, "content_id": content_id})


def test_request_schemas_publish_the_id_pattern_and_bounds() -> None:
    match = ContentMatchRequest.model_json_schema()["properties"]["content_id"]
    assert match["pattern"] == DOCUMENT_ID_PATTERN
    session = CreateSessionRequest.model_json_schema()["properties"]
    assert session["activity_id"]["pattern"] == DOCUMENT_ID_PATTERN
    assert session["activity_id"]["maxLength"] == 100
    duration = session["target_duration_seconds"]["anyOf"][0]
    assert (duration["minimum"], duration["maximum"]) == (300, 86400)
    assert "ge" not in duration
