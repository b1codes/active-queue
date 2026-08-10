from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.core.firestore import close_firestore, get_firestore_client, init_firestore


@pytest.mark.asyncio
async def test_get_firestore_client_uninitialized_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_firestore_client raises RuntimeError if called before initialization."""
    monkeypatch.setattr("app.core.firestore._client", None)
    with pytest.raises(RuntimeError, match="Firestore client not initialized"):
        get_firestore_client()


@pytest.mark.asyncio
async def test_init_firestore_sets_emulator_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_firestore wires emulator host environment variables and initializes client."""
    s = Settings(
        env="local",
        firestore_emulator_host="localhost:9090",
        firebase_auth_emulator_host="localhost:9099",
    )

    try:
        await init_firestore(s)
        assert os.environ.get("FIRESTORE_EMULATOR_HOST") == "localhost:9090"
        assert os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == "localhost:9099"
        client = get_firestore_client()
        assert client is not None
    finally:
        await close_firestore()
        assert "app.core.firestore._client" not in os.environ
