from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from google.cloud.firestore import ArrayUnion
from google.cloud.firestore_v1 import FieldFilter

from app.core.errors import NotFoundError
from app.features.content.models import ContentCacheItem, FeedItem, Source

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

logger = structlog.get_logger(__name__)


# Upper bound on feed_items documents read per GET /content/feed request when a duration
# filter is active. Keeps reads per request bounded; the cursor resumes the scan.
MAX_FEED_SCAN_PER_REQUEST = 500


@dataclass(frozen=True)
class FeedCursor:
    """Position in the feed scan: (published_at, feed doc id) of the last document read.

    The doc id breaks ties between items with identical published_at, which a
    timestamp-only startAfter would silently skip.
    """

    published_at: datetime
    doc_id: str | None = None


def encode_cursor(dt: datetime, doc_id: str | None = None) -> str:
    """Encode a feed cursor to an opaque base64 string."""
    raw = json.dumps({"t": dt.isoformat(), "id": doc_id}) if doc_id else dt.isoformat()
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> FeedCursor | None:
    """Decode an opaque cursor. Accepts the legacy timestamp-only format too."""
    try:
        raw_str = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        if raw_str.startswith("{"):
            payload = json.loads(raw_str)
            return FeedCursor(datetime.fromisoformat(payload["t"]), str(payload["id"]))
        return FeedCursor(datetime.fromisoformat(raw_str))
    except (ValueError, KeyError, TypeError):  # bad base64/UTF-8/JSON/ISO all raise these
        return None


class SourceRepository:
    """Firestore repository for sources collection per SPEC §4.5."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def create_source(self, source: Source) -> Source:
        """Create a source document in sources collection."""
        doc_ref = self._client.collection("sources").document(source.id)
        await doc_ref.set(source.to_firestore())
        logger.info("source_created", source_id=source.id, user_id=source.user_id)
        return source

    async def get_source(self, source_id: str) -> Source | None:
        """Fetch a source by document ID."""
        doc_ref = self._client.collection("sources").document(source_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return Source.from_firestore(data)

    async def get_user_sources(self, user_id: str) -> list[Source]:
        """Fetch all active/syncing sources for a user."""
        query = (
            self._client.collection("sources")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .order_by("updated_at", direction="DESCENDING")
        )
        snapshots = await query.get()
        return [Source.from_firestore(snap.to_dict() or {}) for snap in snapshots]

    async def get_user_source_by_external_id(
        self, user_id: str, provider: str, external_source_id: str
    ) -> Source | None:
        """Check if user has already added a source by provider + external_source_id."""
        query = (
            self._client.collection("sources")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("provider", "==", provider))
            .where(filter=FieldFilter("external_source_id", "==", external_source_id))
            .limit(1)
        )
        snapshots = await query.get()
        if not snapshots:
            return None
        return Source.from_firestore(snapshots[0].to_dict() or {})

    async def update_source(self, source_id: str, updates: dict[str, Any]) -> None:
        """Update fields on a source document."""
        doc_ref = self._client.collection("sources").document(source_id)
        await doc_ref.update(updates)
        logger.info("source_updated", source_id=source_id, fields=list(updates.keys()))

    async def delete_source(self, source_id: str) -> None:
        """Delete a source document from sources collection."""
        doc_ref = self._client.collection("sources").document(source_id)
        await doc_ref.delete()
        logger.info("source_deleted", source_id=source_id)


class ContentRepository:
    """Firestore repository for content_cache and feed_items collections per SPEC §4.6 & §4.7."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def get_content_cache(self, content_id: str) -> ContentCacheItem | None:
        """Fetch single content_cache document by content_id."""
        doc_ref = self._client.collection("content_cache").document(content_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return ContentCacheItem.from_firestore(data)

    async def get_content_cache_batch(self, content_ids: list[str]) -> dict[str, ContentCacheItem]:
        """Fetch a batch of content_cache documents by content_ids."""
        if not content_ids:
            return {}

        results: dict[str, ContentCacheItem] = {}
        refs = [self._client.collection("content_cache").document(cid) for cid in content_ids]
        async for snap in self._client.get_all(refs):
            if snap.exists:
                data = snap.to_dict() or {}
                item = ContentCacheItem.from_firestore(data)
                results[item.content_id] = item

        return results

    async def upsert_content_cache_batch(self, items: list[ContentCacheItem]) -> None:
        """Batch upsert items into content_cache collection (max 500 per batch)."""
        if not items:
            return

        chunk_size = 450
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            batch = self._client.batch()
            for item in chunk:
                doc_ref = self._client.collection("content_cache").document(item.content_id)
                batch.set(doc_ref, item.to_firestore())
            await batch.commit()

        logger.info("content_cache_batch_upserted", count=len(items))

    async def upsert_feed_items_batch(self, items: list[FeedItem]) -> None:
        """Batch upsert items into feed_items collection using deterministic doc IDs."""
        if not items:
            return

        chunk_size = 450
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            batch = self._client.batch()
            for item in chunk:
                doc_ref = self._client.collection("feed_items").document(item.id)
                batch.set(doc_ref, item.to_firestore())
            await batch.commit()

        logger.info("feed_items_batch_upserted", count=len(items))

    async def get_user_feed_count(self, user_id: str) -> int:
        """Compute total unconsumed feed items count using Firestore count() aggregation per SPEC §9.2."""
        query = (
            self._client.collection("feed_items")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("consumed", "==", False))
        )
        count_query = query.count()
        results = await count_query.get()  # type: ignore[call-arg]
        if results and len(results) > 0 and len(results[0]) > 0:
            return int(results[0][0].value)
        return 0

    async def get_user_feed_items_page(
        self,
        user_id: str,
        limit: int = 20,
        cursor: FeedCursor | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
    ) -> tuple[list[FeedItem], str | None]:
        """Fetch paginated unconsumed feed items for user_id using cursor-based pagination.

        Ordered newest first with the doc id as tiebreaker. Duration filters are applied
        in memory, so the query keeps scanning (in batches, up to
        MAX_FEED_SCAN_PER_REQUEST docs) until it finds `limit` matches or runs out.
        next_cursor is non-null whenever unscanned documents remain, even if this page
        holds fewer than `limit` items; clients page until next_cursor is null.
        """
        tie_break = cursor is None or cursor.doc_id is not None
        query = (
            self._client.collection("feed_items")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("consumed", "==", False))
            .order_by("published_at", direction="DESCENDING")
        )
        if tie_break:
            query = query.order_by("__name__", direction="DESCENDING")

        filtered = min_duration is not None or max_duration is not None
        batch_size = 100 if filtered else limit + 1

        results: list[FeedItem] = []
        position = cursor
        scanned = 0
        while True:
            page_query = query
            if position is not None:
                page_query = page_query.start_after(self._cursor_values(position, tie_break))
            snapshots = await page_query.limit(batch_size).get()

            for snap in snapshots:
                item = FeedItem.from_firestore(snap.to_dict() or {})
                scanned += 1
                if (min_duration is not None and item.duration_seconds < min_duration) or (
                    max_duration is not None and item.duration_seconds > max_duration
                ):
                    position = FeedCursor(item.published_at, snap.id)
                    continue
                if len(results) == limit:
                    # A further match exists, so there is definitely a next page.
                    last = results[-1]
                    return results, encode_cursor(last.published_at, last.id)
                results.append(item)
                position = FeedCursor(item.published_at, snap.id)

            if len(snapshots) < batch_size:
                return results, None  # exhausted
            if scanned >= MAX_FEED_SCAN_PER_REQUEST or not filtered:
                break

        if len(results) == limit:
            last = results[-1]
            return results, encode_cursor(last.published_at, last.id)
        if position is None:  # pragma: no cover - a scan that read nothing has exhausted
            return results, None
        return results, encode_cursor(position.published_at, position.doc_id)

    def _cursor_values(self, cursor: FeedCursor, tie_break: bool) -> dict[str, Any]:
        values: dict[str, Any] = {"published_at": cursor.published_at}
        if tie_break and cursor.doc_id:
            values["__name__"] = self._client.collection("feed_items").document(cursor.doc_id)
        return values

    async def get_unconsumed_feed_items_in_range(
        self,
        user_id: str,
        min_duration: int,
        max_duration: int,
        *,
        limit: int,
        descending: bool = False,
    ) -> list[FeedItem]:
        """Unconsumed feed items with min_duration <= duration_seconds <= max_duration.

        Ordered by duration (ascending, or descending), at most `limit` of them, so the
        reads are bounded by the result, not by the size of the user's feed.
        """
        if min_duration > max_duration:
            return []
        query = (
            self._client.collection("feed_items")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("consumed", "==", False))
            .where(filter=FieldFilter("duration_seconds", ">=", min_duration))
            .where(filter=FieldFilter("duration_seconds", "<=", max_duration))
            .order_by("duration_seconds", direction="DESCENDING" if descending else "ASCENDING")
            .limit(limit)
        )
        snapshots = await query.get()
        return [FeedItem.from_firestore(snap.to_dict() or {}) for snap in snapshots]

    async def hide_feed_item(self, user_id: str, content_id: str) -> None:
        """Manually hide feed item by setting consumed = True and adding content_id to user consumed_content_ids per SPEC §9.1 & §9.2."""
        feed_doc_id = f"{user_id}_{content_id}"
        feed_ref = self._client.collection("feed_items").document(feed_doc_id)
        user_ref = self._client.collection("users").document(user_id)

        feed_snap = await feed_ref.get()
        if not feed_snap.exists:
            raise NotFoundError(
                code="CONTENT_NOT_FOUND",
                message=f"Feed item '{content_id}' not found",
            )

        now = datetime.now(UTC)
        batch = self._client.batch()
        batch.update(feed_ref, {"consumed": True, "updated_at": now})
        # merge=True: lands even if users/{uid} was never provisioned.
        batch.set(
            user_ref,
            {"consumed_content_ids": ArrayUnion([content_id]), "updated_at": now},
            merge=True,
        )

        await batch.commit()
        logger.info("feed_item_manually_hidden", user_id=user_id, content_id=content_id)

    async def mark_feed_item_consumed(self, user_id: str, content_id: str) -> None:
        """Mark feed item as consumed by setting consumed = True."""
        doc_id = f"{user_id}_{content_id}"
        doc_ref = self._client.collection("feed_items").document(doc_id)
        snapshot = await doc_ref.get()
        if snapshot.exists:
            await doc_ref.update({"consumed": True})
            logger.info("feed_item_marked_consumed", doc_id=doc_id)
