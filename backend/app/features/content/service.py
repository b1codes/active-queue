from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ProviderError, ValidationError
from app.features.content.models import ContentCacheItem, FeedItem, Source
from app.features.content.repository import ContentRepository, SourceRepository, decode_cursor
from app.features.content.schemas import (
    FeedItemSchema,
    FeedResponse,
    SyncResponse,
    format_duration_label,
)
from app.providers.base import format_content_id, parse_content_id
from app.providers.factory import get_provider

logger = structlog.get_logger(__name__)

# Forbidden system playlist prefixes per SPEC §9.3 & Subtask 5
SYSTEM_PLAYLIST_IDS = ("WL", "LL", "HL")


class ContentService:
    """Business logic for content sources and ingestion per SPEC §5.2, §8.2, §9.2, §9.3 & §9.4.

    Enforces business rules:
    - Max 5 sources per user (SOURCE_LIMIT_REACHED).
    - System playlists (WL, LL, HL) rejected with dedicated error (SOURCE_UNSUPPORTED).
    - Unparseable URL format rejected with (SOURCE_URL_UNPARSEABLE).
    - Private or missing playlist rejected with (SOURCE_NOT_ACCESSIBLE).
    - Duplicate source rejected with (SOURCE_ALREADY_ADDED).
    - Chunked resumable sync processing <= 5 pages (~250 items) per HTTP request.
    - Preflight change detection using itemCount and 7-day full walk force interval.
    - Stalled sync expiration (1 hour timeout).
    - Sync start throttling (15 mins), never throttling continuation chunks.
    - Cursor-based feed pagination with server duration_label formatting.
    - total_unconsumed count aggregation on first page only (cursor is None).
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        content_repo: ContentRepository | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._content_repo = content_repo

    async def add_source(self, user_id: str, url_or_id: str) -> Source:
        """Add a new content source for user_id with strict validation per SPEC §9.3."""
        raw_input = url_or_id.strip()
        if not raw_input:
            raise ValidationError(
                code="SOURCE_URL_UNPARSEABLE",
                message="Source URL or ID cannot be empty",
            )

        # Step 1: Pre-check system playlists (WL, LL, HL)
        extracted_id = raw_input
        match_list = re.search(r"list=([A-Za-z0-9_-]+)", raw_input)
        if match_list:
            extracted_id = match_list.group(1)

        ext_upper = extracted_id.upper()
        if ext_upper in SYSTEM_PLAYLIST_IDS or any(
            ext_upper.startswith(p) for p in SYSTEM_PLAYLIST_IDS
        ):
            raise ValidationError(
                code="SOURCE_UNSUPPORTED",
                message="Watch Later (WL), Liked Videos (LL), and History (HL) system playlists are restricted by YouTube API and cannot be synced.",
            )

        provider_impl = get_provider()

        # Step 2: Validate URL & parse external source ID via provider
        try:
            provider_name, external_id = await provider_impl.validate_source_url(raw_input)
        except ValidationError:
            raise
        except Exception as err:
            raise ValidationError(
                code="SOURCE_URL_UNPARSEABLE",
                message=f"Unable to parse source URL: {err!s}",
            ) from err

        # Step 3: Check max 5 sources guardrail per user
        existing_sources = await self._source_repo.get_user_sources(user_id)
        if len(existing_sources) >= 5:
            raise ValidationError(
                code="SOURCE_LIMIT_REACHED",
                message="Maximum limit of 5 content sources reached",
            )

        # Step 4: Duplicate source check
        duplicate = await self._source_repo.get_user_source_by_external_id(
            user_id, provider_name, external_id
        )
        if duplicate:
            raise ConflictError(
                code="SOURCE_ALREADY_ADDED",
                message="Source has already been added to your account",
            )

        # Step 5: Verify accessibility & fetch metadata
        try:
            meta = await provider_impl.get_playlist_metadata(external_id)
        except NotFoundError as err:
            raise NotFoundError(
                code="SOURCE_NOT_ACCESSIBLE",
                message=f"Source playlist '{external_id}' not found or private",
            ) from err
        except ProviderError:
            raise

        # Step 6: Construct and persist Source object
        source_doc_id = f"{user_id}_{provider_name}_{external_id}"
        now = datetime.now(UTC)

        source = Source(
            id=source_doc_id,
            user_id=user_id,
            provider=provider_name,
            external_source_id=external_id,
            title=meta.title,
            description=meta.description,
            item_count=meta.item_count,
            thumbnail_url=meta.thumbnail_url,
            status="active",
            created_at=now,
            updated_at=now,
        )

        saved_source = await self._source_repo.create_source(source)
        logger.info(
            "source_added_successfully",
            source_id=saved_source.id,
            user_id=user_id,
            title=saved_source.title,
        )
        return saved_source

    async def sync_source_chunk(self, user_id: str, source_id: str) -> SyncResponse:
        """Process one chunk (<= 5 pages / ~250 items) of resumable sync per SPEC §5.2 & §9.4."""
        source = await self._source_repo.get_source(source_id)
        if not source or source.user_id != user_id:
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message=f"Source '{source_id}' not found",
            )

        now = datetime.now(UTC)

        # Step 1: Check stalled sync expiration (1 hour timeout per SPEC §9.4)
        if source.status == "syncing" and source.updated_at:
            elapsed_stalled = (now - source.updated_at).total_seconds()
            if elapsed_stalled > settings.sync_stall_timeout_seconds:
                logger.warning(
                    "sync_stalled_reset", source_id=source_id, elapsed_seconds=elapsed_stalled
                )
                source.status = "active"
                source.next_page_token = None

        # Step 2: Preflight Change Detection (1 unit check) — only on NEW sync start
        is_resuming = bool(source.next_page_token)
        provider_impl = get_provider(source.provider)

        if not is_resuming:
            if source.last_sync_at:
                elapsed_since_last = (now - source.last_sync_at).total_seconds()
                if elapsed_since_last < settings.sync_throttle_seconds:
                    logger.info(
                        "sync_start_throttled",
                        source_id=source_id,
                        elapsed_seconds=elapsed_since_last,
                    )
                    return SyncResponse(
                        source_id=source_id,
                        status=source.status,
                        items_synced=0,
                        has_more=False,
                        next_page_token=None,
                        message="Sync throttled: source was synced recently",
                    )

            try:
                meta = await provider_impl.get_playlist_metadata(source.external_source_id)
            except (NotFoundError, ProviderError) as err:
                source.status = "error"
                source.error_message = str(err)
                await self._source_repo.update_source(
                    source.id,
                    {"status": "error", "error_message": str(err), "updated_at": now},
                )
                raise

            force_full_walk = False
            if not source.last_sync_at:
                force_full_walk = True
            else:
                days_since_walk = (now - source.last_sync_at).days
                if days_since_walk >= settings.full_walk_interval_days:
                    force_full_walk = True

            if (
                not force_full_walk
                and source.item_count is not None
                and meta.item_count == source.item_count
            ):
                logger.info(
                    "sync_preflight_no_change", source_id=source_id, item_count=source.item_count
                )
                await self._source_repo.update_source(
                    source.id,
                    {"last_sync_at": now, "status": "active", "updated_at": now},
                )
                return SyncResponse(
                    source_id=source_id,
                    status="active",
                    items_synced=0,
                    has_more=False,
                    next_page_token=None,
                    message="No changes detected in preflight check",
                )

        # Step 3: Execute Chunked Walk (<= 5 pages, max 250 items)
        current_token = source.next_page_token
        chunk_cache_items: list[ContentCacheItem] = []
        chunk_feed_items: list[FeedItem] = []

        pages_fetched = 0
        total_items_in_chunk = 0

        while pages_fetched < settings.pages_per_chunk:
            try:
                page = await provider_impl.fetch_playlist_items(
                    source.external_source_id,
                    page_token=current_token,
                    max_results=50,
                )
            except Exception as err:
                logger.error("sync_fetch_error", source_id=source_id, error=str(err))
                await self._source_repo.update_source(
                    source.id,
                    {"status": "error", "error_message": str(err), "updated_at": now},
                )
                raise

            pages_fetched += 1

            for raw in page.items:
                cid = format_content_id(source.provider, raw.external_id)

                cache_item = ContentCacheItem(
                    content_id=cid,
                    provider=source.provider,
                    external_id=raw.external_id,
                    title=raw.title,
                    duration_seconds=raw.duration_seconds,
                    published_at=raw.published_at,
                    thumbnail_url=raw.thumbnail_url,
                    video_url=raw.video_url,
                    is_available=(raw.duration_seconds > 0 or "Private" not in raw.title),
                    created_at=now,
                    updated_at=now,
                )
                chunk_cache_items.append(cache_item)

                feed_item = FeedItem(
                    id=f"{user_id}_{cid}",
                    user_id=user_id,
                    content_id=cid,
                    source_id=source.id,
                    published_at=raw.published_at,
                    duration_seconds=raw.duration_seconds,
                    consumed=False,
                    created_at=now,
                    updated_at=now,
                )
                chunk_feed_items.append(feed_item)

            total_items_in_chunk += len(page.items)
            current_token = page.next_page_token

            if not current_token:
                break

        # Step 4: Write batch to Firestore & update Source state atomically
        if self._content_repo:
            await self._content_repo.upsert_content_cache_batch(chunk_cache_items)
            await self._content_repo.upsert_feed_items_batch(chunk_feed_items)

        is_complete = current_token is None
        new_status = "active" if is_complete else "syncing"

        update_dict = {
            "status": new_status,
            "next_page_token": current_token,
            "updated_at": now,
        }
        if is_complete:
            update_dict["last_sync_at"] = now

        await self._source_repo.update_source(source.id, update_dict)

        logger.info(
            "sync_chunk_completed",
            source_id=source_id,
            items_synced=total_items_in_chunk,
            has_more=not is_complete,
            next_page_token=current_token,
        )

        return SyncResponse(
            source_id=source.id,
            status=new_status,
            items_synced=total_items_in_chunk,
            has_more=not is_complete,
            next_page_token=current_token,
            message="Chunk sync complete" if not is_complete else "Full sync complete",
        )

    async def get_user_feed(
        self,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
    ) -> FeedResponse:
        """Fetch user feed items with cursor pagination, duration filters, and server duration_label per SPEC §9.2."""
        if not self._content_repo:
            return FeedResponse(items=[], next_cursor=None, total_unconsumed=0)

        # Compute total_unconsumed count aggregation ONLY on first page per SPEC §9.2
        total_unconsumed: int | None = None
        if cursor is None:
            total_unconsumed = await self._content_repo.get_user_feed_count(user_id)

        # Decode cursor to datetime
        cursor_dt = decode_cursor(cursor) if cursor else None

        # Fetch feed items page
        feed_items, next_cursor = await self._content_repo.get_user_feed_items_page(
            user_id=user_id,
            limit=limit,
            cursor_dt=cursor_dt,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        if not feed_items:
            return FeedResponse(
                items=[],
                next_cursor=next_cursor,
                total_unconsumed=total_unconsumed,
            )

        # Fetch matching content_cache documents
        content_ids = [fi.content_id for fi in feed_items]
        cache_map = await self._content_repo.get_content_cache_batch(content_ids)

        # Enrich feed items into FeedItemSchema
        enriched_items: list[FeedItemSchema] = []
        for fi in feed_items:
            cache_doc = cache_map.get(fi.content_id)

            provider_name = "fixture"
            external_id = fi.content_id
            if ":" in fi.content_id:
                provider_name, external_id = parse_content_id(fi.content_id)

            title = cache_doc.title if cache_doc else f"Feed Video {external_id}"
            thumb_url = cache_doc.thumbnail_url if cache_doc else None
            vid_url = cache_doc.video_url if cache_doc else None

            enriched_items.append(
                FeedItemSchema(
                    id=fi.id,
                    content_id=fi.content_id,
                    source_id=fi.source_id,
                    title=title,
                    provider=provider_name,
                    external_id=external_id,
                    duration_seconds=fi.duration_seconds,
                    duration_label=format_duration_label(fi.duration_seconds),
                    published_at=fi.published_at,
                    thumbnail_url=thumb_url,
                    video_url=vid_url,
                    consumed=fi.consumed,
                )
            )

        return FeedResponse(
            items=enriched_items,
            next_cursor=next_cursor,
            total_unconsumed=total_unconsumed,
        )
