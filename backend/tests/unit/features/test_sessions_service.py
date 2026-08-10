from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.features.content.models import ContentCacheItem
from app.features.sessions.models import Session
from app.features.sessions.service import SessionService


@pytest.mark.asyncio
async def test_create_session_reads_duration_from_content_cache() -> None:
    """Content duration is read from content_cache, NEVER from request body per SPEC §9.5."""
    mock_session_repo = MagicMock()
    mock_session_repo.get_active_user_session = AsyncMock(return_value=None)
    mock_session_repo.create_session = AsyncMock(side_effect=lambda s: s)

    mock_content_repo = MagicMock()
    cache_doc = ContentCacheItem(
        content_id="fx:10",
        provider="fixture",
        external_id="10",
        title="Workout Video",
        duration_seconds=1800,  # 30 mins
        published_at=datetime.now(UTC),
    )
    mock_content_repo.get_content_cache = AsyncMock(return_value=cache_doc)

    service = SessionService(mock_session_repo, content_repo=mock_content_repo)
    session = await service.create_session(
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:10",
    )

    assert session.duration_seconds == 1800
    assert session.status == "pending"


@pytest.mark.asyncio
async def test_create_session_bare_time_first_validates_allowlist() -> None:
    """Bare time-first session duration validated against 7 time block allowlist."""
    mock_session_repo = MagicMock()
    mock_session_repo.get_active_user_session = AsyncMock(return_value=None)
    mock_session_repo.create_session = AsyncMock(side_effect=lambda s: s)

    service = SessionService(mock_session_repo)

    # Valid 30m block (1800s)
    session = await service.create_session(
        user_id="u1",
        activity_id="running",
        match_mode="time_first",
        target_duration_seconds=1800,
    )
    assert session.duration_seconds == 1800

    # Invalid non-allowlist block (700s)
    with pytest.raises(ValidationError) as exc_info:
        await service.create_session(
            user_id="u1",
            activity_id="running",
            match_mode="time_first",
            target_duration_seconds=700,
        )
    assert exc_info.value.code == "DURATION_OUT_OF_RANGE"


@pytest.mark.asyncio
async def test_create_session_single_active_session_guardrail() -> None:
    """Only one non-terminal session per user; second returns ACTIVE_SESSION_EXISTS (409)."""
    mock_session_repo = MagicMock()
    existing_session = Session(
        id="s_active",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="in_progress",
    )
    mock_session_repo.get_active_user_session = AsyncMock(return_value=existing_session)

    service = SessionService(mock_session_repo)
    with pytest.raises(ConflictError) as exc_info:
        await service.create_session(
            user_id="u1",
            activity_id="running",
            match_mode="time_first",
            target_duration_seconds=1800,
        )

    assert exc_info.value.code == "ACTIVE_SESSION_EXISTS"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_start_session_cross_user_returns_404() -> None:
    """Cross-user session access returns SESSION_NOT_FOUND (404), NOT 403."""
    mock_session_repo = MagicMock()
    other_user_session = Session(
        id="s_other",
        user_id="u_other",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="pending",
    )
    mock_session_repo.get_session = AsyncMock(return_value=other_user_session)

    service = SessionService(mock_session_repo)
    with pytest.raises(NotFoundError) as exc_info:
        await service.start_session(user_id="u_attacker", session_id="s_other")

    assert exc_info.value.code == "SESSION_NOT_FOUND"
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_start_session_idempotent_refire() -> None:
    """Re-firing start on an in_progress session preserves original started_at."""
    mock_session_repo = MagicMock()
    original_start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    in_progress_session = Session(
        id="s_prog",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="in_progress",
        started_at=original_start,
    )
    mock_session_repo.get_session = AsyncMock(return_value=in_progress_session)

    service = SessionService(mock_session_repo)
    res = await service.start_session("u1", "s_prog")

    assert res.status == "in_progress"
    assert res.started_at == original_start


@pytest.mark.asyncio
async def test_complete_session_v11_fields_rejection() -> None:
    """Providing external_workout_url or healthkit_uuid returns 501 FEATURE_NOT_AVAILABLE."""
    mock_session_repo = MagicMock()
    service = SessionService(mock_session_repo)

    with pytest.raises(AppError) as exc_info:
        await service.complete_session(
            user_id="u1",
            session_id="s1",
            external_workout_url="https://strava.com/activity/123",
        )
    assert exc_info.value.code == "FEATURE_NOT_AVAILABLE"
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
async def test_complete_session_idempotent_and_status_rules() -> None:
    """Completing completed session is idempotent (200 OK); completing pending session returns SESSION_NOT_STARTED (409)."""
    mock_session_repo = MagicMock()

    # 1. Idempotent completed session
    completed_session = Session(
        id="s_comp",
        user_id="u1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:1",
        duration_seconds=1800,
        status="completed",
    )
    mock_session_repo.complete_session_transaction = AsyncMock(return_value=completed_session)

    service = SessionService(mock_session_repo)
    res = await service.complete_session("u1", "s_comp")
    assert res.status == "completed"

    # 2. Completing pending session returns 409 SESSION_NOT_STARTED
    mock_session_repo.complete_session_transaction = AsyncMock(
        side_effect=ConflictError(
            code="SESSION_NOT_STARTED", message="Session has not been started yet"
        )
    )
    with pytest.raises(ConflictError) as exc_info:
        await service.complete_session("u1", "s_pending")
    assert exc_info.value.code == "SESSION_NOT_STARTED"
    assert exc_info.value.status_code == 409
