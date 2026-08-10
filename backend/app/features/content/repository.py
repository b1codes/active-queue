from __future__ import annotations

import base64
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


def encode_cursor(dt: datetime) -> str:
    """Encode datetime cursor to base64 string."""
    iso_str = dt.isoformat()
    return base64.urlsafe_b64encode(iso_str.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> datetime | None:
    """Decode base64 cursor string into datetime object."""
    try:
        raw_str = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        return datetime.fromisoformat(raw_str)
    except Exception:
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
            .where(field_path="user_id", op_string="==", value=user_id)
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
            .where(field_path="user_id", op_string="==", value=user_id)
            .where(field_path="provider", op_string="==", value=provider)
            .where(field_path="external_source_id", op_string="==", value=external_source_id)
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
        cursor_dt: datetime | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
    ) -> tuple[list[FeedItem], str | None]:
        """Fetch paginated unconsumed feed items for user_id using cursor-based pagination."""
        query = (
            self._client.collection("feed_items")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("consumed", "==", False))
            .order_by("published_at", direction="DESCENDING")
        )

        if cursor_dt is not None:
            query = query.start_after({"published_at": cursor_dt})

        fetch_limit = (
            limit + 1 if (min_duration is None and max_duration is None) else min(limit * 3, 100)
        )
        query = query.limit(fetch_limit)

        snapshots = await query.get()
        results: list[FeedItem] = []
        for snap in snapshots:
            data = snap.to_dict() or {}
            item = FeedItem.from_firestore(data)

            if min_duration is not None and item.duration_seconds < min_duration:
                continue
            if max_duration is not None and item.duration_seconds > max_duration:
                continue

            results.append(item)
            if len(results) == limit:
                break

        next_cursor: str | None = None
        if len(results) == limit and len(snapshots) > limit:
            last_item = results[-1]
            next_cursor = encode_cursor(last_item.published_at)

        return results, next_cursor

    async def get_all_unconsumed_feed_items(self, user_id: str) -> list[FeedItem]:
        """Fetch all unconsumed feed items for user_id to perform time-first matching."""
        query = (
            self._client.collection("feed_items")
            .where(field_path="user_id", op_string="==", value=user_id)
            .where(field_path="consumed", op_string="==", value=False)
            .order_by("duration_seconds", direction="ASCENDING")
            .limit(250)
        )
        snapshots = await query.get()
        return [FeedItem.from_firestore(snap.to_dict() or {}) for snap in snapshots]

    async def hide_feed_item(self, user_id: str, content_id: str) -> None:
        """Manually hide feed item by setting consumed = True and adding content_id to user consumed_content per SPEC §9.1 & §9.2."""
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
        batch.update(
            user_ref,
            {"consumed_content": ArrayUnion([content_id]), "updated_at": now},
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
