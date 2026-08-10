from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_source_invalid_input_returns_400(
    mock_firestore_client: MagicMock,
) -> None:
    """POST /api/v1/sources with empty or control character payload returns 400 VALIDATION_FAILED."""
    mock_decoded = {"uid": "test_user_val_1", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            resp = await client.post(
                "/api/v1/sources",
                json={"url_or_id": "<script>alert(1)</script>   "},
            )

    assert resp.status_code == 400
    json_body = resp.json()
    assert json_body["status"] == "error"
    assert json_body["error"]["code"] == "VALIDATION_FAILED"
    assert "details" in json_body["error"]


@pytest.mark.asyncio
async def test_update_preferences_out_of_range_time_block_returns_400(
    mock_firestore_client: MagicMock,
) -> None:
    """PATCH /api/v1/users/me/preferences with time block out of bounds returns 400."""
    mock_decoded = {"uid": "test_user_val_2", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            resp = await client.patch(
                "/api/v1/users/me/preferences",
                json={"default_time_block_seconds": 10},  # less than ge=300
            )

    assert resp.status_code == 400
    json_body = resp.json()
    assert json_body["status"] == "error"
    assert json_body["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_create_session_invalid_activity_id_returns_400(
    mock_firestore_client: MagicMock,
) -> None:

    """POST /api/v1/sessions with control chars in activity_id returns 400."""
    mock_decoded = {"uid": "test_user_val_3", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            resp = await client.post(
                "/api/v1/sessions",
                json={
                    "activity_id": "\x00\x07",
                    "match_mode": "content_first",
                },
            )

    assert resp.status_code == 400
    json_body = resp.json()
    assert json_body["status"] == "error"
    assert json_body["error"]["code"] == "VALIDATION_FAILED"
