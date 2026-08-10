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
    PlaylistMetadata,
    PlaylistPage,
    RawContentItem,
)

logger = structlog.get_logger(__name__)

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

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total_seconds


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

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        """Fetch playlist metadata from YouTube Data API v3 playlists.list."""
        if not self._api_key:
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message="YouTube API key is not configured",
            )

        url = "https://www.googleapis.com/youtube/v3/playlists"
        params = {
            "part": "snippet,contentDetails",
            "id": source_id,
            "key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)

        if resp.status_code == 403:
            body = resp.json().get("error", {})
            errors = body.get("errors", [])
            reason = errors[0].get("reason") if errors else ""
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise ProviderError(
                    code="PROVIDER_QUOTA_EXCEEDED",
                    message="YouTube Data API quota limit exceeded",
                )
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message=f"YouTube API error: {body.get('message', 'Forbidden')}",
            )

        if resp.status_code != 200:
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message=f"YouTube API returned HTTP {resp.status_code}",
            )

        data = resp.json()
        items = data.get("items", [])
        if not items:
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message=f"YouTube playlist '{source_id}' not found or private",
            )

        snippet = items[0].get("snippet", {})
        content_details = items[0].get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        thumb_url = thumbnails.get("high", {}).get("url") or thumbnails.get("default", {}).get(
            "url"
        )

        return PlaylistMetadata(
            source_id=source_id,
            title=snippet.get("title", "Untitled Playlist"),
            description=snippet.get("description"),
            item_count=content_details.get("itemCount"),
            thumbnail_url=thumb_url,
        )

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
    ) -> PlaylistPage:
        """Fetch page of playlist items via playlistItems.list and videos.list.

        Handles the silent case where private/deleted videos are absent from videos.list.
        """
        if not self._api_key:
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message="YouTube API key is not configured",
            )

        # Step 1: Fetch playlist items page (1 unit)
        items_url = "https://www.googleapis.com/youtube/v3/playlistItems"
        items_params: dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": source_id,
            "maxResults": min(max_results, 50),
            "key": self._api_key,
        }
        if page_token:
            items_params["pageToken"] = page_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(items_url, params=items_params)

        if resp.status_code == 403:
            body = resp.json().get("error", {})
            errors = body.get("errors", [])
            reason = errors[0].get("reason") if errors else ""
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise ProviderError(
                    code="PROVIDER_QUOTA_EXCEEDED",
                    message="YouTube Data API quota limit exceeded",
                )
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message=f"YouTube API error: {body.get('message', 'Forbidden')}",
            )

        if resp.status_code != 200:
            raise ProviderError(
                code="PROVIDER_UNAVAILABLE",
                message=f"YouTube API returned HTTP {resp.status_code}",
            )

        items_data = resp.json()
        raw_playlist_items = items_data.get("items", [])
        next_page_token = items_data.get("nextPageToken")
        total_results = items_data.get("pageInfo", {}).get("totalResults")

        if not raw_playlist_items:
            return PlaylistPage(
                items=[],
                next_page_token=next_page_token,
                total_results=total_results,
            )

        # Extract video IDs for videos.list call
        video_ids: list[str] = []
        video_id_to_snippet: dict[str, dict[str, Any]] = {}
        for item in raw_playlist_items:
            snippet = item.get("snippet", {})
            res_id = snippet.get("resourceId", {})
            vid_id = res_id.get("videoId") or item.get("contentDetails", {}).get("videoId")
            if vid_id:
                video_ids.append(vid_id)
                video_id_to_snippet[vid_id] = snippet

        if not video_ids:
            return PlaylistPage(
                items=[],
                next_page_token=next_page_token,
                total_results=total_results,
            )

        # Step 2: Batch fetch video details for duration & status (1 unit)
        videos_url = "https://www.googleapis.com/youtube/v3/videos"
        videos_params = {
            "part": "contentDetails,snippet",
            "id": ",".join(video_ids),
            "key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            videos_resp = await client.get(videos_url, params=videos_params)

        video_details_map: dict[str, dict[str, Any]] = {}
        if videos_resp.status_code == 200:
            videos_data = videos_resp.json()
            for v_item in videos_data.get("items", []):
                v_id = v_item.get("id")
                if v_id:
                    video_details_map[v_id] = v_item

        # Step 3: Combine and handle silent missing private/deleted videos per SPEC §8.3
        result_items: list[RawContentItem] = []
        for vid_id in video_ids:
            snippet = video_id_to_snippet.get(vid_id, {})
            v_details = video_details_map.get(vid_id)

            if not v_details:
                # Private or deleted video absent from videos.list per SPEC §8.3
                title = snippet.get("title", "[Private or Deleted Video]")
                result_items.append(
                    RawContentItem(
                        external_id=vid_id,
                        title=title,
                        duration_seconds=0,
                        published_at=datetime.now(UTC),
                        thumbnail_url=None,
                        video_url=f"https://www.youtube.com/watch?v={vid_id}",
                    )
                )
                continue

            v_snippet = v_details.get("snippet", {})
            v_content = v_details.get("contentDetails", {})
            iso_duration = v_content.get("duration")
            duration_secs = parse_iso8601_duration(iso_duration)

            pub_str = v_snippet.get("publishedAt") or snippet.get("publishedAt")
            try:
                pub_dt = (
                    datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    if pub_str
                    else datetime.now(UTC)
                )
            except ValueError:
                pub_dt = datetime.now(UTC)

            thumbs = v_snippet.get("thumbnails", {}) or snippet.get("thumbnails", {})
            thumb_url = thumbs.get("high", {}).get("url") or thumbs.get("default", {}).get("url")

            result_items.append(
                RawContentItem(
                    external_id=vid_id,
                    title=v_snippet.get("title") or snippet.get("title", "Untitled Video"),
                    duration_seconds=duration_secs,
                    published_at=pub_dt,
                    thumbnail_url=thumb_url,
                    video_url=f"https://www.youtube.com/watch?v={vid_id}",
                )
            )

        return PlaylistPage(
            items=result_items,
            next_page_token=next_page_token,
            total_results=total_results,
        )
