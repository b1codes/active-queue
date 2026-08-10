from __future__ import annotations

import pytest

from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.providers.factory import get_provider
from app.providers.fixture import FixtureProvider


@pytest.mark.asyncio
async def test_fixture_provider_validate_source_url() -> None:
    """FixtureProvider.validate_source_url parses playlist URLs and fixture IDs."""
    provider = FixtureProvider()

    res1 = await provider.validate_source_url("https://www.youtube.com/playlist?list=PL123456789")
    assert res1 == ("fixture", "PL123456789")

    res2 = await provider.validate_source_url("fixture:my-test-playlist")
    assert res2 == ("fixture", "my-test-playlist")

    res3 = await provider.validate_source_url("fixture-large-playlist")
    assert res3 == ("fixture", "fixture-large-playlist")

    with pytest.raises(ValidationError) as exc_info:
        await provider.validate_source_url("https://invalid-url.com/something")
    assert exc_info.value.code == "SOURCE_URL_UNPARSEABLE"


@pytest.mark.asyncio
async def test_fixture_provider_metadata() -> None:
    """FixtureProvider retrieves metadata for small, empty, and large playlists."""
    provider = FixtureProvider()

    meta_large = await provider.get_playlist_metadata("fixture-large-playlist")
    assert meta_large.item_count == 1200
    assert "1,200" in meta_large.title

    meta_small = await provider.get_playlist_metadata("fixture-small-playlist")
    assert meta_small.item_count == 15

    meta_empty = await provider.get_playlist_metadata("fixture-empty-playlist")
    assert meta_empty.item_count == 0


@pytest.mark.asyncio
async def test_fixture_provider_quota_and_unavailable_triggers() -> None:
    """FixtureProvider triggers quotaExceeded and unavailable errors on magic IDs."""
    provider = FixtureProvider()

    with pytest.raises(ProviderError) as exc_quota:
        await provider.get_playlist_metadata("fixture-quota-exceeded")
    assert exc_quota.value.code == "PROVIDER_QUOTA_EXCEEDED"
    assert exc_quota.value.status_code == 503

    with pytest.raises(NotFoundError) as exc_unavail:
        await provider.get_playlist_metadata("fixture-unavailable")
    assert exc_unavail.value.code == "SOURCE_NOT_FOUND"
    assert exc_unavail.value.status_code == 404


@pytest.mark.asyncio
async def test_fixture_provider_pagination_1200_items() -> None:
    """FixtureProvider paginates across 1,200 items across multiple pages."""
    provider = FixtureProvider()

    # Page 1 (0 to 50)
    page1 = await provider.fetch_playlist_items(
        "fixture-large-playlist", page_token=None, max_results=50
    )
    assert len(page1.items) == 50
    assert page1.next_page_token == "50"
    assert page1.total_results == 1200

    # Page 2 (50 to 100)
    page2 = await provider.fetch_playlist_items(
        "fixture-large-playlist", page_token=page1.next_page_token, max_results=50
    )
    assert len(page2.items) == 50
    assert page2.next_page_token == "100"

    # Edge cases in corpus
    assert page1.items[10].title == "[Private video]"
    assert page1.items[20].title == "[Deleted video]"
    assert page1.items[30].duration_seconds == 0  # Live stream


@pytest.mark.asyncio
async def test_get_provider_factory() -> None:
    """get_provider returns FixtureProvider instance when requested or default."""
    p = get_provider("fixture")
    assert isinstance(p, FixtureProvider)
