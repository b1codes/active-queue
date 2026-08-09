from __future__ import annotations

import time
from collections import OrderedDict
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.features.users.models import UserAuthorization


class AuthorizationCache:
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
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[UserAuthorization, float]] = OrderedDict()

    def get(self, uid: str) -> UserAuthorization | None:
        """Fetch cached authorization for uid if present and not expired."""
        if uid not in self._cache:
            return None

        auth_doc, timestamp = self._cache[uid]
        if time.time() - timestamp > self._ttl_seconds:
            # Expired — evict
            del self._cache[uid]
            return None

        # Move to end (LRU)
        self._cache.move_to_end(uid)
        return auth_doc

    def set(self, uid: str, auth_doc: UserAuthorization) -> None:
        """Store authorization for uid in cache, evicting oldest if max_entries exceeded."""
        if uid in self._cache:
            del self._cache[uid]

        elif len(self._cache) >= self._max_entries:
            # Evict oldest (first item in OrderedDict)
            self._cache.popitem(last=False)

        self._cache[uid] = (auth_doc, time.time())

    def invalidate(self, uid: str) -> None:
        """Evict authorization cache entry for uid."""
        self._cache.pop(uid, None)

    def clear(self) -> None:
        """Clear all entries from authorization cache."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


# Global singleton instance for the process
auth_cache = AuthorizationCache()
