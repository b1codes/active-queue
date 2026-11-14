"""Count the Firestore reads and writes the app is billed for, per request.

Firestore bills per document read and per document write, so the number of documents a
request touches is both its cost and most of its latency. The emulator tier's perf tests
(`tests/emulator/test_read_budgets_emulator.py`, `test_sync_cost_emulator.py`) wrap the
SDK's gRPC client with this meter and hold every endpoint to a budget.

The meter sits on the generated gRPC client (`FirestoreAsyncClient`), which every SDK call
goes through: queries, document gets, `get_all`, aggregations, batches and transactions.
It counts what the server returns, following Firestore's billing rules:

- a query is billed one read per document returned, and one read if it returns none,
- a document get is billed one read per document requested, found or not (conservative),
- a `count()` aggregation is billed one read per 1,000 index entries matched, minimum one,
- a commit is billed one write per write in it (deletes included).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from google.cloud.firestore_v1.services.firestore.async_client import FirestoreAsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    import pytest


@dataclass
class Usage:
    """Billed operations since the last reset."""

    reads: int = 0
    writes: int = 0
    queries: int = 0
    rpcs: int = 0
    # Reads per collection, to point at the query that blew a budget.
    by_collection: Counter[str] = field(default_factory=Counter)

    def describe(self) -> str:
        cols = ", ".join(f"{c}={n}" for c, n in self.by_collection.most_common())
        return (
            f"{self.reads} reads ({cols or 'none'}), {self.writes} writes, "
            f"{self.queries} queries, {self.rpcs} RPCs"
        )


def _get(request: Any, name: str) -> Any:
    if isinstance(request, dict):
        return request.get(name)
    return getattr(request, name, None)


def _query_collection(request: Any) -> str:
    query = _get(request, "structured_query")
    try:
        return str(query.from_[0].collection_id)
    except (AttributeError, IndexError, TypeError):
        return "?"


def _doc_collection(path: str) -> str:
    # projects/p/databases/d/documents/<collection>/<id>[/...]
    parts = path.split("/documents/", 1)[-1].split("/")
    return parts[-2] if len(parts) >= 2 else "?"


class _CountingStream:
    """Wraps a gRPC response stream and counts what it yields."""

    def __init__(
        self, stream: Any, on_response: Callable[[Any], None], on_end: Callable[[], None]
    ):
        self._stream = stream
        self._on_response = on_response
        self._on_end = on_end

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Any]:
        try:
            async for response in self._stream:
                self._on_response(response)
                yield response
        finally:
            self._on_end()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class FirestoreMeter:
    """Install with `install(monkeypatch)`; read `usage`, then `reset()` between requests."""

    def __init__(self) -> None:
        self.usage = Usage()

    def reset(self) -> None:
        self.usage = Usage()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meter = self
        run_query = FirestoreAsyncClient.run_query
        batch_get = FirestoreAsyncClient.batch_get_documents
        aggregation = FirestoreAsyncClient.run_aggregation_query
        commit = FirestoreAsyncClient.commit

        def wrap_stream(
            original: Callable[..., Awaitable[Any]],
            on_start: Callable[[Any], tuple[Callable[[Any], None], Callable[[], None]]],
        ) -> Callable[..., Awaitable[Any]]:
            def wrapped(self: Any, *args: Any, **kwargs: Any) -> Awaitable[Any]:
                request = kwargs.get("request", args[0] if args else None)
                meter.usage.rpcs += 1
                on_response, on_end = on_start(request)
                pending = original(self, *args, **kwargs)

                async def counted() -> _CountingStream:
                    return _CountingStream(await pending, on_response, on_end)

                return counted()

            return wrapped

        def query_counter(request: Any) -> tuple[Callable[[Any], None], Callable[[], None]]:
            collection = _query_collection(request)
            meter.usage.queries += 1
            seen = [0]

            def on_response(response: Any) -> None:
                if response._pb.HasField("document"):
                    seen[0] += 1

            def on_end() -> None:
                billed = max(1, seen[0])
                meter.usage.reads += billed
                meter.usage.by_collection[collection] += billed

            return on_response, on_end

        def get_counter(request: Any) -> tuple[Callable[[Any], None], Callable[[], None]]:
            for path in _get(request, "documents") or []:
                meter.usage.reads += 1
                meter.usage.by_collection[_doc_collection(path)] += 1
            return (lambda _r: None), (lambda: None)

        def aggregation_counter(
            request: Any,
        ) -> tuple[Callable[[Any], None], Callable[[], None]]:
            nested = _get(request, "structured_aggregation_query")
            collection = _query_collection({"structured_query": nested.structured_query})
            meter.usage.queries += 1
            matched = [0]

            def on_response(response: Any) -> None:
                if response._pb.HasField("result"):
                    for value in response.result.aggregate_fields.values():
                        matched[0] = max(matched[0], int(value.integer_value))

            def on_end() -> None:
                billed = max(1, math.ceil(matched[0] / 1000))
                meter.usage.reads += billed
                meter.usage.by_collection[collection] += billed

            return on_response, on_end

        async def counted_commit(self: Any, *args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request", args[0] if args else None)
            meter.usage.rpcs += 1
            meter.usage.writes += len(_get(request, "writes") or [])
            return await commit(self, *args, **kwargs)

        monkeypatch.setattr(
            FirestoreAsyncClient, "run_query", wrap_stream(run_query, query_counter)
        )
        monkeypatch.setattr(
            FirestoreAsyncClient, "batch_get_documents", wrap_stream(batch_get, get_counter)
        )
        monkeypatch.setattr(
            FirestoreAsyncClient,
            "run_aggregation_query",
            wrap_stream(aggregation, aggregation_counter),
        )
        monkeypatch.setattr(FirestoreAsyncClient, "commit", counted_commit)
