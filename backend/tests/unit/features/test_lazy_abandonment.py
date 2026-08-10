from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ConflictError
from app.features.sessions.models import Session
from app.features.sessions.service import SessionService


@pytest.mark.asyncio
async def test_lazy_abandonment_on_read() -> None:
    """Session created > 24h + duration_seconds ago is lazily marked abandoned on read per SPEC §7.2."""
    now = datetime(2026, 8, 9, 20, 0, 0, tzinfo=UTC)
    # Created 25 hours ago with 1800s duration -> cutoff was 24h 30m ago
    created_old = now - timedelta(hours=25)

    old_session = Session(
        id="s_old",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="pending",
        created_at=created_old,
    )

    mock_doc = MagicMock()
    mock_doc.update = AsyncMock()
    mock_snap = MagicMock()
    mock_snap.to_dict.return_value = old_session.to_firestore()

    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_query.get = AsyncMock(return_value=[mock_snap])
    mock_query.where.return_value = mock_query
    mock_query.limit.return_value = mock_query

    mock_collection = MagicMock()
    mock_collection.where.return_value = mock_query
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    from app.features.sessions.repository import SessionRepository

    repo = SessionRepository(mock_client)
    res = await repo.get_active_user_session("u1", now=now)

    # Lazily marked abandoned, so active session returns None!
    assert res is None
    mock_doc.update.assert_called_once()
    assert mock_doc.update.call_args[0][0]["status"] == "abandoned"


@pytest.mark.asyncio
async def test_explicit_abandon_session() -> None:
    """Explicit abandon_session transitions session to abandoned status."""
    mock_session_repo = MagicMock()
    abandoned_session = Session(
        id="s_ab",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="abandoned",
        abandoned_at=datetime.now(UTC),
    )
    mock_session_repo.abandon_session = AsyncMock(return_value=abandoned_session)

    service = SessionService(mock_session_repo)
    res = await service.abandon_session("u1", "s_ab")

    assert res.status == "abandoned"
    assert res.abandoned_at is not None


@pytest.mark.asyncio
async def test_abandon_completed_session_raises_409() -> None:
    """Abandoning a completed session raises SESSION_ALREADY_TERMINAL (409)."""
    mock_session_repo = MagicMock()
    mock_session_repo.abandon_session = AsyncMock(
        side_effect=ConflictError(
            code="SESSION_ALREADY_TERMINAL", message="Completed session cannot be abandoned"
        )
    )

    service = SessionService(mock_session_repo)
    with pytest.raises(ConflictError) as exc_info:
        await service.abandon_session("u1", "s_completed")

    assert exc_info.value.code == "SESSION_ALREADY_TERMINAL"
    assert exc_info.value.status_code == 409
