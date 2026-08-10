from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ConflictError
from app.features.sessions.models import Session
from app.features.sessions.service import SessionService


@pytest.mark.asyncio
async def test_discard_pending_session_hard_deletes() -> None:
    """discard_session hard deletes pending session document per Decision #6 & SPEC §9.5."""
    mock_session_repo = MagicMock()
    mock_session_repo.discard_session = AsyncMock(return_value=None)

    service = SessionService(mock_session_repo)
    res = await service.discard_session("u1", "s_pending_1")

    assert res == {"session_id": "s_pending_1", "discarded": True}
    mock_session_repo.discard_session.assert_called_once_with("s_pending_1", "u1")


@pytest.mark.asyncio
async def test_discard_in_progress_session_raises_409() -> None:
    """Attempting to discard an in_progress session raises SESSION_ALREADY_STARTED (409)."""
    mock_session_repo = MagicMock()
    mock_session_repo.discard_session = AsyncMock(
        side_effect=ConflictError(
            code="SESSION_ALREADY_STARTED", message="Cannot discard in_progress session"
        )
    )

    service = SessionService(mock_session_repo)
    with pytest.raises(ConflictError) as exc_info:
        await service.discard_session("u1", "s_in_prog")

    assert exc_info.value.code == "SESSION_ALREADY_STARTED"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_discard_completed_session_raises_409() -> None:
    """Attempting to discard a completed session raises SESSION_ALREADY_TERMINAL (409)."""
    mock_session_repo = MagicMock()
    mock_session_repo.discard_session = AsyncMock(
        side_effect=ConflictError(
            code="SESSION_ALREADY_TERMINAL", message="Cannot discard terminal session"
        )
    )

    service = SessionService(mock_session_repo)
    with pytest.raises(ConflictError) as exc_info:
        await service.discard_session("u1", "s_comp")

    assert exc_info.value.code == "SESSION_ALREADY_TERMINAL"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_user_sessions_history() -> None:
    """get_user_sessions returns paginated SessionListResponse."""
    mock_session_repo = MagicMock()
    session_item = Session(
        id="s_hist_1",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="completed",
    )
    mock_session_repo.get_user_sessions_page = AsyncMock(
        return_value=([session_item], "cursor_abc")
    )

    service = SessionService(mock_session_repo)
    res = await service.get_user_sessions("u1", limit=10)

    assert len(res.items) == 1
    assert res.items[0].id == "s_hist_1"
    assert res.next_cursor == "cursor_abc"
