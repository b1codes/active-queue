"""complete_session_transaction under transaction contention (SPEC §7.1 double taps).

These run the real google-cloud-firestore async_transactional retry loop; only the
transaction's RPCs (begin, commit, rollback) and document reads are faked. Faking the
decorator itself once hid that exhausted retries surface as ValueError, not Aborted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import Aborted

from app.features.sessions.repository import COMPLETE_TXN_ATTEMPTS, SessionRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _ContendedTransaction:
    """Stands in for AsyncTransaction: every commit loses to a concurrent writer."""

    def __init__(self, max_attempts: int, *, abort_reads: bool = False) -> None:
        self._max_attempts = max_attempts
        self._read_only = False
        self._id: bytes | None = None
        self.abort_reads = abort_reads
        self.commits = 0
        self.rollbacks = 0

    def _clean_up(self) -> None:
        self._id = None

    async def _begin(self, retry_id: bytes | None = None) -> None:
        self._id = b"txn"

    async def _commit(self) -> list[Any]:
        self.commits += 1
        raise Aborted("too much contention")

    async def _rollback(self) -> None:
        self.rollbacks += 1

    def update(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def _snap(data: dict[str, Any] | None) -> MagicMock:
    snap = MagicMock()
    snap.exists = data is not None
    snap.to_dict.return_value = data
    return snap


def _repo(
    after_contention: dict[str, Any] | None, *, abort_reads: bool = False
) -> tuple[SessionRepository, MagicMock, list[_ContendedTransaction]]:
    """A repo whose transactional reads see an in-progress session and whose plain
    (post-contention) read sees `after_contention`."""
    in_txn = _snap(_session("in_progress"))
    after = _snap(after_contention)
    txns: list[_ContendedTransaction] = []

    async def get(*, transaction: Any = None) -> MagicMock:
        if transaction is None:
            return after
        if transaction.abort_reads:
            raise Aborted("read lost to a concurrent writer")
        return in_txn

    def transaction(max_attempts: int) -> _ContendedTransaction:
        txns.append(_ContendedTransaction(max_attempts, abort_reads=abort_reads))
        return txns[-1]

    client = MagicMock()
    client.collection.return_value.document.return_value.get = AsyncMock(side_effect=get)
    client.transaction.side_effect = transaction
    return SessionRepository(client), client, txns


def _session(status: str, user_id: str = "u1") -> dict[str, Any]:
    return {
        "id": "s1",
        "user_id": user_id,
        "activity_id": "running",
        "match_mode": "time_first",
        "duration_seconds": 900,
        "status": status,
        "created_at": NOW,
        "updated_at": NOW,
        "completed_at": NOW if status == "completed" else None,
    }


async def test_exhausted_retries_resolve_to_the_winning_complete() -> None:
    repo, client, txns = _repo(_session("completed"))
    session = await repo.complete_session_transaction("s1", "u1", NOW)
    assert session.status == "completed"
    assert session.completed_at == NOW
    client.transaction.assert_called_once_with(max_attempts=COMPLETE_TXN_ATTEMPTS)
    assert txns[0].commits == COMPLETE_TXN_ATTEMPTS


async def test_an_aborted_read_resolves_to_the_winning_complete() -> None:
    repo, _, txns = _repo(_session("completed"), abort_reads=True)
    session = await repo.complete_session_transaction("s1", "u1", NOW)
    assert session.status == "completed"
    assert txns[0].commits == 0


@pytest.mark.parametrize(
    "data",
    [None, _session("in_progress"), _session("completed", user_id="someone-else")],
    ids=["missing", "not-completed", "other-user"],
)
async def test_contention_without_a_completed_session_still_fails(
    data: dict[str, Any] | None,
) -> None:
    repo, _, _ = _repo(data)
    with pytest.raises(ValueError, match="attempts") as excinfo:
        await repo.complete_session_transaction("s1", "u1", NOW)
    assert isinstance(excinfo.value.__cause__, Aborted)


async def test_an_unrelated_value_error_is_not_treated_as_contention() -> None:
    repo, client, _ = _repo(_session("completed"))
    client.collection.return_value.document.return_value.get = AsyncMock(
        side_effect=ValueError("bad document path")
    )
    with pytest.raises(ValueError, match="bad document path"):
        await repo.complete_session_transaction("s1", "u1", NOW)
