from __future__ import annotations

from app.core.cache import TTLCache
from app.core.config import settings
from app.features.users.models import UserAuthorization


class AuthorizationCache(TTLCache[UserAuthorization]):
    """In-process LRU + TTL cache for user authorization lookups per SPEC §3.2.

    Prevents extra Firestore read overhead (~5-15 ms) on every authenticated request.
    Bounds account deactivation staleness to max 60 seconds (auth_cache_ttl_seconds).
    Per-instance in-memory cache — not a correctness dependency (cache miss reads through).
    """

    def __init__(
        self,
        ttl_seconds: int = settings.auth_cache_ttl_seconds,
        max_entries: int = 1000,
    ) -> None:
        super().__init__(ttl_seconds=ttl_seconds, max_entries=max_entries)


# Global singleton instance for the process
auth_cache = AuthorizationCache()
