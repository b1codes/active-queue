from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import NotFoundError
from app.features.content.service import ContentService


@pytest.mark.asyncio
async def test_hide_feed_item_calls_repository() -> None:
    """hide_feed_item calls repository to mark feed item consumed and update user consumed_content."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()
    mock_content_repo.hide_feed_item = AsyncMock(return_value=None)

    service = ContentService(mock_source_repo, mock_content_repo)
    res = await service.hide_feed_item("u1", "fx:99")

    assert res == {"content_id": "fx:99", "hidden": True}
    mock_content_repo.hide_feed_item.assert_called_once_with("u1", "fx:99")


@pytest.mark.asyncio
async def test_hide_feed_item_not_found_raises_404() -> None:
    """Missing feed item throws CONTENT_NOT_FOUND (404)."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()
    mock_content_repo.hide_feed_item = AsyncMock(
        side_effect=NotFoundError(code="CONTENT_NOT_FOUND", message="Feed item not found")
    )

    service = ContentService(mock_source_repo, mock_content_repo)
    with pytest.raises(NotFoundError) as exc_info:
        await service.hide_feed_item("u1", "fx:nonexistent")

    assert exc_info.value.code == "CONTENT_NOT_FOUND"
    assert exc_info.value.status_code == 404
