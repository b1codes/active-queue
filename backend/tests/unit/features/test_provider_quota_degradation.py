from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import ProviderError
from app.features.content.models import Source
from app.features.content.service import ContentService


@pytest.mark.asyncio
async def test_provider_quota_degradation_preserves_cursor() -> None:
    """When YouTube Data API returns PROVIDER_QUOTA_EXCEEDED, source status becomes quota_paused and next_page_token cursor is preserved per SPEC §8.3."""
    mock_source_repo = AsyncMock()
    mock_content_repo = AsyncMock()

    source = Source(
        id="usr_1_yt_PL123",
        user_id="usr_1",
        provider="youtube",
        external_source_id="PL123",
        title="Test Playlist",
        status="syncing",
        next_page_token="cursor_token_page_3",
    )
    mock_source_repo.get_source.return_value = source

    mock_provider = AsyncMock()
    mock_provider.fetch_playlist_items.side_effect = ProviderError(
        code="PROVIDER_QUOTA_EXCEEDED",
        message="YouTube Data API quota limit exceeded",
    )

    service = ContentService(source_repo=mock_source_repo, content_repo=mock_content_repo)

    with (
        patch("app.features.content.service.get_provider", return_value=mock_provider),
        pytest.raises(ProviderError) as exc_info,
    ):
        await service.sync_source_chunk("usr_1", "usr_1_yt_PL123")

    assert exc_info.value.code == "PROVIDER_QUOTA_EXCEEDED"

    # Verify source update preserved status='quota_paused' while not wiping next_page_token cursor
    mock_source_repo.update_source.assert_called_once()
    args, _kwargs = mock_source_repo.update_source.call_args
    assert args[0] == "usr_1_yt_PL123"
    update_dict = args[1]
    assert update_dict["status"] == "quota_paused"
    assert "next_page_token" not in update_dict  # Cursor remains intact!
