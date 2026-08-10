from __future__ import annotations

from app.core.config import settings
from app.providers.base import ContentProvider
from app.providers.fixture import FixtureProvider
from app.providers.youtube import YouTubeProvider


def get_provider(provider_name: str | None = None) -> ContentProvider:
    """Provider factory function selecting ContentProvider implementation per SPEC §8.4.

    Defaults to settings.content_provider ("fixture" or "youtube").
    """
    target_provider = (provider_name or settings.content_provider).lower()
    if target_provider == "fixture":
        return FixtureProvider()
    elif target_provider == "youtube":
        return YouTubeProvider()
    else:
        # Fallback to FixtureProvider for unknown/dev provider names
        return FixtureProvider()
