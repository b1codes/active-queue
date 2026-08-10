from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.features.content.models import Source
from app.features.content.service import ContentService


@pytest.mark.asyncio
async def test_add_source_success() -> None:
    """ContentService.add_source adds valid content source."""
    mock_repo = MagicMock()
    mock_repo.get_user_sources = AsyncMock(return_value=[])
    mock_repo.get_user_source_by_external_id = AsyncMock(return_value=None)
    mock_repo.create_source = AsyncMock(side_effect=lambda s: s)

    service = ContentService(mock_repo)
    source = await service.add_source("user1", "fixture-small-playlist")

    assert source.user_id == "user1"
    assert source.provider == "fixture"
    assert source.external_source_id == "fixture-small-playlist"
    assert source.status == "active"


@pytest.mark.asyncio
async def test_add_source_system_playlists_rejection() -> None:
    """ContentService.add_source rejects WL, LL, HL system playlists per SPEC §9.3."""
    mock_repo = MagicMock()
    service = ContentService(mock_repo)

    for sys_id in (
        "WL",
        "LL",
        "HL",
        "WL_my_list",
        "LL12345",
        "https://youtube.com/playlist?list=WL",
    ):
        with pytest.raises(ValidationError) as exc_info:
            await service.add_source("user1", sys_id)
        assert exc_info.value.code == "SOURCE_UNSUPPORTED"
        assert "restricted by YouTube API" in exc_info.value.message


@pytest.mark.asyncio
async def test_add_source_max_sources_limit() -> None:
    """ContentService.add_source rejects when user has 5 existing sources."""
    mock_repo = MagicMock()
    mock_repo.get_user_sources = AsyncMock(return_value=[MagicMock()] * 5)

    service = ContentService(mock_repo)
    with pytest.raises(ValidationError) as exc_info:
        await service.add_source("user1", "fixture-small-playlist")
    assert exc_info.value.code == "SOURCE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_add_source_duplicate_check() -> None:
    """ContentService.add_source rejects duplicate source for same user."""
    mock_repo = MagicMock()
    mock_repo.get_user_sources = AsyncMock(return_value=[])
    existing_source = Source(
        id="user1_fixture_fixture-small-playlist",
        user_id="user1",
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Small Playlist",
    )
    mock_repo.get_user_source_by_external_id = AsyncMock(return_value=existing_source)

    service = ContentService(mock_repo)
    with pytest.raises(ConflictError) as exc_info:
        await service.add_source("user1", "fixture-small-playlist")
    assert exc_info.value.code == "SOURCE_ALREADY_ADDED"


@pytest.mark.asyncio
async def test_add_source_not_accessible() -> None:
    """ContentService.add_source converts NotFoundError to SOURCE_NOT_ACCESSIBLE."""
    mock_repo = MagicMock()
    mock_repo.get_user_sources = AsyncMock(return_value=[])
    mock_repo.get_user_source_by_external_id = AsyncMock(return_value=None)

    service = ContentService(mock_repo)
    with pytest.raises(NotFoundError) as exc_info:
        await service.add_source("user1", "fixture-unavailable")
    assert exc_info.value.code == "SOURCE_NOT_ACCESSIBLE"
