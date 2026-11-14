"""Sync and add-source failure handling: every provider failure leaves the source in a
truthful state (SPEC §8.3, §9.4) and surfaces the right error code."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.features.content.models import Source
from app.features.content.service import ContentService
from app.providers.base import KnownLookup, PlaylistMetadata, PlaylistPage


class StubProvider:
    def __init__(
        self,
        *,
        validate: Exception | None = None,
        meta: Exception | PlaylistMetadata | None = None,
        fetch: Exception | None = None,
    ) -> None:
        self._validate, self._meta, self._fetch = validate, meta, fetch

    async def validate_source_url(self, url: str) -> tuple[str, str]:
        if self._validate:
            raise self._validate
        return "fixture", url

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        if isinstance(self._meta, Exception):
            raise self._meta
        return self._meta or PlaylistMetadata(source_id=source_id, title="t", item_count=99)

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
        *,
        known: KnownLookup | None = None,
    ) -> PlaylistPage:
        if self._fetch:
            raise self._fetch
        return PlaylistPage(items=[], next_page_token=None)


def _service(source: Source | None = None) -> tuple[ContentService, AsyncMock]:
    source_repo = AsyncMock()
    source_repo.get_source.return_value = source
    source_repo.get_user_sources.return_value = []
    source_repo.get_user_source_by_external_id.return_value = None
    source_repo.create_source.side_effect = lambda s: s
    user_repo = AsyncMock()
    user_repo.get_consumed_content_ids.return_value = set()
    return ContentService(source_repo, AsyncMock(), user_repo), source_repo


def _source(**kw: Any) -> Source:
    base: dict[str, Any] = {
        "id": "u1_fixture_pl",
        "user_id": "u1",
        "provider": "fixture",
        "external_source_id": "pl",
        "title": "t",
        "item_count": 10,
    }
    return Source(**{**base, **kw})


def _last_update(repo: AsyncMock) -> dict[str, Any]:
    update: dict[str, Any] = repo.update_source.call_args.args[1]
    return update


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderError("PROVIDER_QUOTA_EXCEEDED", "q"), "quota_paused"),
        (ProviderError("PROVIDER_UNAVAILABLE", "down"), "error"),
        (NotFoundError("SOURCE_NOT_FOUND", "gone"), "error"),
    ],
)
async def test_preflight_failure_marks_source(error: Exception, status: str) -> None:
    service, repo = _service(_source())
    with (
        patch("app.features.content.service.get_provider", return_value=StubProvider(meta=error)),
        pytest.raises(type(error)),
    ):
        await service.sync_source_chunk("u1", "u1_fixture_pl")
    assert _last_update(repo)["status"] == status


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderError("PROVIDER_QUOTA_EXCEEDED", "q"), "quota_paused"),
        (ProviderError("PROVIDER_UNAVAILABLE", "down"), "error"),
        (RuntimeError("unexpected"), "error"),
    ],
)
async def test_page_fetch_failure_marks_source_and_keeps_cursor(
    error: Exception, status: str
) -> None:
    # Resuming (cursor set) skips the preflight and goes straight to the page fetch.
    service, repo = _service(_source(next_page_token="250", status="syncing"))
    with (
        patch("app.features.content.service.get_provider", return_value=StubProvider(fetch=error)),
        pytest.raises(type(error)),
    ):
        await service.sync_source_chunk("u1", "u1_fixture_pl")
    update = _last_update(repo)
    assert update["status"] == status
    assert "next_page_token" not in update  # cursor retained for resume


async def test_unchanged_item_count_skips_the_walk() -> None:
    service, repo = _service(_source(last_sync_at=datetime.now(UTC) - timedelta(hours=2)))
    meta = PlaylistMetadata(source_id="pl", title="t", item_count=10)
    with patch("app.features.content.service.get_provider", return_value=StubProvider(meta=meta)):
        res = await service.sync_source_chunk("u1", "u1_fixture_pl")
    assert res.items_synced == 0
    assert _last_update(repo)["status"] == "active"


async def test_add_source_rejects_blank_input() -> None:
    service, _ = _service()
    with pytest.raises(ValidationError) as exc:
        await service.add_source("u1", "   ")
    assert exc.value.code == "SOURCE_URL_UNPARSEABLE"


async def test_add_source_wraps_unexpected_parse_errors() -> None:
    service, _ = _service()
    stub = StubProvider(validate=RuntimeError("regex exploded"))
    with (
        patch("app.features.content.service.get_provider", return_value=stub),
        pytest.raises(ValidationError) as exc,
    ):
        await service.add_source("u1", "PLabc")
    assert exc.value.code == "SOURCE_URL_UNPARSEABLE"


async def test_add_source_propagates_provider_outage() -> None:
    service, repo = _service()
    stub = StubProvider(meta=ProviderError("PROVIDER_UNAVAILABLE", "down"))
    with (
        patch("app.features.content.service.get_provider", return_value=stub),
        pytest.raises(ProviderError),
    ):
        await service.add_source("u1", "PLabc")
    repo.create_source.assert_not_called()
