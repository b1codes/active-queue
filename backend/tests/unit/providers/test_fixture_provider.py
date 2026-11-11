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
    # 50 playlist slots, but private #10 and deleted #20 are absent (as on YouTube)
    assert len(page1.items) == 48
    assert {"vid_private_10", "vid_deleted_20"}.isdisjoint(i.external_id for i in page1.items)
    assert page1.next_page_token == "50"
    assert page1.total_results == 1200

    # Page 2 (50 to 100)
    page2 = await provider.fetch_playlist_items(
        "fixture-large-playlist", page_token=page1.next_page_token, max_results=50
    )
    assert len(page2.items) == 50
    assert page2.next_page_token == "100"

    # Edge cases in corpus: the live stream is still returned, with duration 0
    live = next(i for i in page1.items if i.external_id == "vid_livestream_30")
    assert live.duration_seconds == 0


@pytest.mark.asyncio
async def test_get_provider_factory() -> None:
    """get_provider returns FixtureProvider instance when requested or default."""
    p = get_provider("fixture")
    assert isinstance(p, FixtureProvider)


@pytest.mark.asyncio
async def test_fixture_provider_page_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each page waits page_latency_ms (the E2E stack's stand-in for the Data API)."""
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("app.providers.fixture.asyncio.sleep", fake_sleep)
    await FixtureProvider(page_latency_ms=150).fetch_playlist_items("fixture-small-playlist")
    await FixtureProvider().fetch_playlist_items("fixture-small-playlist")
    assert waits == [0.15]


def test_get_provider_passes_fixture_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    """The factory hands settings.fixture_page_latency_ms to the fixture provider."""
    monkeypatch.setattr("app.providers.factory.settings.fixture_page_latency_ms", 250)
    provider = get_provider("fixture")
    assert isinstance(provider, FixtureProvider)
    assert provider._page_latency_s == 0.25


def test_fixture_page_latency_is_bounded() -> None:
    """A typo can't stall every sync: the setting is capped at 5 s and never negative."""
    from pydantic import ValidationError as PydanticValidationError

    from app.core.config import Settings

    assert Settings(fixture_page_latency_ms=5000).fixture_page_latency_ms == 5000
    for bad in (-1, 5001):
        with pytest.raises(PydanticValidationError):
            Settings(fixture_page_latency_ms=bad)
