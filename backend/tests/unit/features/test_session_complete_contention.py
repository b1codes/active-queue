"""complete_session_transaction under transaction contention (SPEC §7.1 double taps)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import Aborted

from app.features.sessions.repository import COMPLETE_TXN_ATTEMPTS, SessionRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _always_aborts(_fn: Any) -> Any:
    async def run(_txn: Any) -> Any:
        raise Aborted("too much contention")

    return run


def _repo(snapshot_data: dict[str, Any] | None) -> tuple[SessionRepository, MagicMock]:
    client = MagicMock()
    snap = MagicMock()
    snap.exists = snapshot_data is not None
    snap.to_dict.return_value = snapshot_data
    client.collection.return_value.document.return_value.get = AsyncMock(return_value=snap)
    return SessionRepository(client), client


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


@pytest.fixture(autouse=True)
def _abort_every_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.sessions.repository.async_transactional", _always_aborts)


async def test_contention_resolves_to_the_winning_complete() -> None:
    repo, client = _repo(_session("completed"))
    session = await repo.complete_session_transaction("s1", "u1", NOW)
    assert session.status == "completed"
    assert session.completed_at == NOW
    client.transaction.assert_called_once_with(max_attempts=COMPLETE_TXN_ATTEMPTS)


@pytest.mark.parametrize(
    "data",
    [None, _session("in_progress"), _session("completed", user_id="someone-else")],
    ids=["missing", "not-completed", "other-user"],
)
async def test_contention_without_a_completed_session_still_fails(
    data: dict[str, Any] | None,
) -> None:
    repo, _ = _repo(data)
    with pytest.raises(Aborted):
        await repo.complete_session_transaction("s1", "u1", NOW)
