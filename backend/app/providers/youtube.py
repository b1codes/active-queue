from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.providers.base import (
    ContentProvider,
    KnownLookup,
    PlaylistMetadata,
    PlaylistPage,
    RawContentItem,
)

logger = structlog.get_logger(__name__)

API_BASE = "https://www.googleapis.com/youtube/v3"

# ISO-8601 Duration Regex: P[n]DT[n]H[n]M[n]S
ISO_DURATION_REGEX = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_iso8601_duration(duration_str: str | None) -> int:
    """Parse ISO-8601 duration strings (e.g. PT45M, PT1H2M3S, PT10S, P0D) into total seconds.

    Per SPEC §8.4:
    - PT45M -> 2700
    - PT1H2M3S -> 3723
    - PT10S -> 10
    - P0D -> 0 (live streams)
    - Absent/None -> 0
    """
    if not duration_str:
        return 0

    match = ISO_DURATION_REGEX.match(duration_str)
    if not match:
        return 0

    parts = match.groupdict()
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTubeProvider(ContentProvider):
    """YouTube Data API v3 provider adapter per SPEC §8.1-§8.4.

    Important constraints:
    - search.list is STRICTLY FORBIDDEN (100 quota units per call per SPEC §8.3).
    - Private/deleted videos absent from videos.list must be handled gracefully.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.youtube_api_key

    async def validate_source_url(self, url: str) -> tuple[str, str]:
        """Validate URL and extract (provider_name="youtube", external_source_id)."""
        url = url.strip()
        if not url:
            raise ValidationError(
                code="SOURCE_URL_UNPARSEABLE",
                message="YouTube URL cannot be empty",
            )

        # Match playlist URL list=PL...
        match_list = re.search(r"list=([A-Za-z0-9_-]+)", url)
        if match_list:
            return "youtube", match_list.group(1)

        # Match channel URL /channel/UC...
        match_channel = re.search(r"channel/([A-Za-z0-9_-]+)", url)
        if match_channel:
            return "youtube", match_channel.group(1)

        # Direct source ID format PL... or UC...
        if re.match(r"^(PL|UC|UU|FL|RD)[A-Za-z0-9_-]+$", url):
            return "youtube", url

        raise ValidationError(
            code="SOURCE_URL_UNPARSEABLE",
            message=f"Unable to parse YouTube playlist or channel ID from URL '{url}'",
        )

    async def _api_get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET a Data API v3 endpoint, mapping failures onto the SPEC §9.7 error codes.

        - 403 quotaExceeded / dailyLimitExceeded -> PROVIDER_QUOTA_EXCEEDED (503)
        - 404 playlistNotFound -> SOURCE_NOT_FOUND (404)
        - timeouts, transport errors, any other non-200 -> PROVIDER_UNAVAILABLE (503)
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
        except httpx.HTTPError as err:
            logger.warning("youtube_transport_error", url=url, error_type=type(err).__name__)
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message="YouTube API is unreachable",
            ) from err

        if resp.status_code == 200:
            body: dict[str, Any] = resp.json()
            return body

        try:
            error_body = resp.json().get("error", {}) or {}
        except ValueError:
            error_body = {}
        errors = error_body.get("errors") or [{}]
        reason = errors[0].get("reason", "")

        if resp.status_code == 403 and reason in ("quotaExceeded", "dailyLimitExceeded"):
            raise ProviderError(
                code="PROVIDER_QUOTA_EXCEEDED",
                message="YouTube Data API quota limit exceeded",
            )
        if resp.status_code == 404 and reason == "playlistNotFound":
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message="YouTube playlist not found or private",
            )
        raise ProviderError(
            code="PROVIDER_UNAVAILABLE",
            message=f"YouTube API returned HTTP {resp.status_code}",
        )

    def _require_key(self) -> str:
        if not self._api_key:
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message="YouTube API key is not configured",
            )
        return self._api_key

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        """Fetch playlist metadata from YouTube Data API v3 playlists.list (1 unit)."""
        data = await self._api_get(
            f"{API_BASE}/playlists",
            {"part": "snippet,contentDetails", "id": source_id, "key": self._require_key()},
        )
        items = data.get("items", [])
        if not items:
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message=f"YouTube playlist '{source_id}' not found or private",
            )

        snippet = items[0].get("snippet", {})
        content_details = items[0].get("contentDetails", {})
        return PlaylistMetadata(
            source_id=source_id,
            title=snippet.get("title", "Untitled Playlist"),
            description=snippet.get("description"),
            item_count=content_details.get("itemCount"),
            thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
        )

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
        *,
        known: KnownLookup | None = None,
    ) -> PlaylistPage:
        """Fetch one page via playlistItems.list + videos.list (1 unit each).

        Private and deleted videos still appear in playlistItems.list but are silently
        absent from videos.list (SPEC §12.3). They are unplayable, so they are omitted
        from the page rather than emitted with a null duration and a made-up timestamp.

        IDs `known` returns are left out of videos.list, which is skipped (saving its
        unit) when every video on the page is known (SPEC §8.2 step 4).
        """
        key = self._require_key()
        params: dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": source_id,
            "maxResults": min(max_results, 50),
            "key": key,
        }
        if page_token:
            params["pageToken"] = page_token
        items_data = await self._api_get(f"{API_BASE}/playlistItems", params)

        next_page_token = items_data.get("nextPageToken")
        total_results = items_data.get("pageInfo", {}).get("totalResults")

        video_ids: list[str] = []
        playlist_snippets: dict[str, dict[str, Any]] = {}
        for item in items_data.get("items", []):
            snippet = item.get("snippet", {})
            vid_id = snippet.get("resourceId", {}).get("videoId") or item.get(
                "contentDetails", {}
            ).get("videoId")
            if vid_id and vid_id not in playlist_snippets:
                video_ids.append(vid_id)
                playlist_snippets[vid_id] = snippet

        known_ids: list[str] = []
        if known is not None and video_ids:
            already = set(await known(list(video_ids)))
            known_ids = [v for v in video_ids if v in already]
            video_ids = [v for v in video_ids if v not in already]

        if not video_ids:
            return PlaylistPage(
                items=[],
                next_page_token=next_page_token,
                total_results=total_results,
                known_ids=known_ids,
            )

        videos_data = await self._api_get(
            f"{API_BASE}/videos",
            {"part": "contentDetails,snippet", "id": ",".join(video_ids), "key": key},
        )
        details = {v["id"]: v for v in videos_data.get("items", []) if v.get("id")}

        result_items: list[RawContentItem] = []
        for vid_id in video_ids:
            video = details.get(vid_id)
            if video is None:
                logger.info("youtube_video_unavailable_skipped", video_id=vid_id)
                continue
            v_snippet = video.get("snippet", {})
            p_snippet = playlist_snippets[vid_id]
            result_items.append(
                RawContentItem(
                    external_id=vid_id,
                    title=v_snippet.get("title") or p_snippet.get("title") or "Untitled Video",
                    duration_seconds=parse_iso8601_duration(
                        video.get("contentDetails", {}).get("duration")
                    ),
                    published_at=_parse_timestamp(
                        v_snippet.get("publishedAt") or p_snippet.get("publishedAt")
                    ),
                    thumbnail_url=_best_thumbnail(
                        v_snippet.get("thumbnails") or p_snippet.get("thumbnails")
                    ),
                    video_url=f"https://www.youtube.com/watch?v={vid_id}",
                )
            )

        return PlaylistPage(
            items=result_items,
            next_page_token=next_page_token,
            total_results=total_results,
            known_ids=known_ids,
        )


def _best_thumbnail(thumbnails: dict[str, Any] | None) -> str | None:
    thumbs = thumbnails or {}
    for size in ("high", "medium", "default"):
        url = (thumbs.get(size) or {}).get("url")
        if url:
            return str(url)
    return None


def _parse_timestamp(value: str | None) -> datetime:
    """Parse an RFC 3339 API timestamp. Unparseable values fall back to the epoch, not now().

    now() would give the item a new published_at on every sync, making it jump to the top
    of the newest-first feed each time.
    """
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.warning("youtube_unparseable_timestamp", value=value)
    return datetime(1970, 1, 1, tzinfo=UTC)
