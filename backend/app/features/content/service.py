from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog

from app.core.errors import ConflictError, NotFoundError, ProviderError, ValidationError
from app.features.content.models import Source
from app.features.content.repository import SourceRepository
from app.providers.factory import get_provider

logger = structlog.get_logger(__name__)

# Forbidden system playlist prefixes per SPEC §9.3 & Subtask 5
SYSTEM_PLAYLIST_IDS = ("WL", "LL", "HL")


class ContentService:
    """Business logic for content sources and ingestion per SPEC §9.3.

    Enforces business rules:
    - Max 5 sources per user (SOURCE_LIMIT_REACHED).
    - System playlists (WL, LL, HL) rejected with dedicated error (SOURCE_UNSUPPORTED).
    - Unparseable URL format rejected with (SOURCE_URL_UNPARSEABLE).
    - Private or missing playlist rejected with (SOURCE_NOT_ACCESSIBLE).
    - Duplicate source rejected with (SOURCE_ALREADY_ADDED).
    """

    def __init__(self, source_repo: SourceRepository) -> None:
        self._source_repo = source_repo

    async def add_source(self, user_id: str, url_or_id: str) -> Source:
        """Add a new content source for user_id with strict validation per SPEC §9.3."""
        raw_input = url_or_id.strip()
        if not raw_input:
            raise ValidationError(
                code="SOURCE_URL_UNPARSEABLE",
                message="Source URL or ID cannot be empty",
            )

        # Step 1: Pre-check system playlists (WL, LL, HL) in raw input or extracted list param
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

        # Provider resolution
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
