from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_activities_endpoint() -> None:
    """GET /api/v1/activities returns list of 9 activities in house envelope per SPEC §9.5."""
    mock_decoded = {"uid": "test_user_act_1", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.get("/api/v1/activities")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["data"]["activities"]) == 9
    act_ids = [act["id"] for act in data["data"]["activities"]]
    assert "running" in act_ids
    assert "yoga" in act_ids


@pytest.mark.asyncio
async def test_get_time_blocks_endpoint() -> None:
    """GET /api/v1/activities/time-blocks returns list of 7 time blocks in house envelope per SPEC §9.5."""
    mock_decoded = {"uid": "test_user_act_1", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.get("/api/v1/activities/time-blocks")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["data"]["time_blocks"]) == 7
    tb_ids = [tb["id"] for tb in data["data"]["time_blocks"]]
    assert "tb_30m" in tb_ids
    assert "tb_60m" in tb_ids
