from __future__ import annotations

import time
from collections import OrderedDict


class TTLCache[V]:
    """In-process LRU + TTL cache keyed by uid.

    Per-instance and never a correctness dependency: a miss reads through to the source.
    The TTL bounds how stale a cached value can be on a warm instance.
    """

    def __init__(self, ttl_seconds: int, max_entries: int = 1000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[V, float]] = OrderedDict()

    def get(self, uid: str) -> V | None:
        """Fetch the cached value for uid if present and not expired."""
        if uid not in self._cache:
            return None

        value, timestamp = self._cache[uid]
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[uid]
            return None

        self._cache.move_to_end(uid)
        return value

    def set(self, uid: str, value: V) -> None:
        """Store value for uid, evicting the least recently used entry when full."""
        if uid in self._cache:
            del self._cache[uid]
        elif len(self._cache) >= self._max_entries:
            self._cache.popitem(last=False)

        self._cache[uid] = (value, time.time())

    def invalidate(self, uid: str) -> None:
        self._cache.pop(uid, None)

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
