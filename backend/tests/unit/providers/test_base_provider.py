from __future__ import annotations

from datetime import UTC

import pytest

from app.core.errors import ValidationError
from app.providers.base import (
    PlaylistMetadata,
    PlaylistPage,
    RawContentItem,
    format_content_id,
    parse_content_id,
)


def test_format_content_id() -> None:
    """format_content_id generates namespaced IDs with correct prefixes per SPEC §4.1."""
    assert format_content_id("youtube", "dQw4w9WgXcQ") == "yt:dQw4w9WgXcQ"
    assert format_content_id("spotify", "ep_12345") == "sp:ep_12345"
    assert format_content_id("fixture", "fx_item_1") == "fx:fx_item_1"
    assert format_content_id("custom", "abc") == "custom:abc"


def test_parse_content_id_success() -> None:
    """parse_content_id cleanly extracts provider and external_id."""
    provider, ext_id = parse_content_id("yt:dQw4w9WgXcQ")
    assert provider == "youtube"
    assert ext_id == "dQw4w9WgXcQ"

    provider_sp, ext_id_sp = parse_content_id("sp:ep_12345")
    assert provider_sp == "spotify"
    assert ext_id_sp == "ep_12345"

    provider_fx, ext_id_fx = parse_content_id("fx:item_99")
    assert provider_fx == "fixture"
    assert ext_id_fx == "item_99"


def test_parse_content_id_invalid_formats() -> None:
    """parse_content_id raises ValidationError for invalid namespaced IDs."""
    with pytest.raises(ValidationError) as exc_info1:
        parse_content_id("no_colon_here")
    assert exc_info1.value.code == "SOURCE_URL_UNPARSEABLE"

    with pytest.raises(ValidationError) as exc_info2:
        parse_content_id(":missing_prefix")
    assert exc_info2.value.code == "SOURCE_URL_UNPARSEABLE"

    with pytest.raises(ValidationError) as exc_info3:
        parse_content_id("prefix_only:")
    assert exc_info3.value.code == "SOURCE_URL_UNPARSEABLE"


def test_provider_data_models() -> None:
    """PlaylistMetadata, RawContentItem, and PlaylistPage models instantiate cleanly."""
    from datetime import datetime

    item = RawContentItem(
        external_id="vid1",
        title="Test Video",
        duration_seconds=600,
        published_at=datetime.now(UTC),
    )
    page = PlaylistPage(items=[item], next_page_token="token_xyz", total_results=1)
    meta = PlaylistMetadata(source_id="pl123", title="Test Playlist", item_count=1)

    assert item.external_id == "vid1"
    assert page.items[0].title == "Test Video"
    assert meta.source_id == "pl123"
