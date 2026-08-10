from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_default_local_env() -> None:
    """Settings default to local environment with emulator hosts set."""
    s = Settings(
        env="local",
        firestore_emulator_host="localhost:9090",
        firebase_auth_emulator_host="localhost:9099",
    )
    assert s.env == "local"
    assert s.firestore_emulator_host == "localhost:9090"
    assert s.firebase_auth_emulator_host == "localhost:9099"
    assert s.gcp_project_id == "demo-activequeue-local"


def test_settings_prod_disallows_firestore_emulator() -> None:
    """CRITICAL SECURITY GUARDRAIL: prod env raises error if firestore_emulator_host is set."""
    with pytest.raises(
        (ValueError, ValidationError), match="FIRESTORE_EMULATOR_HOST must be UNSET"
    ):
        Settings(
            env="prod",
            firestore_emulator_host="localhost:9090",
            firebase_auth_emulator_host=None,
        )


def test_settings_prod_disallows_firebase_auth_emulator() -> None:
    """CRITICAL SECURITY GUARDRAIL: prod env raises error if firebase_auth_emulator_host is set."""
    with pytest.raises(
        (ValueError, ValidationError), match="FIREBASE_AUTH_EMULATOR_HOST must be UNSET"
    ):
        Settings(
            env="prod",
            firestore_emulator_host=None,
            firebase_auth_emulator_host="localhost:9099",
        )


def test_settings_prod_valid_when_emulators_unset() -> None:
    """prod env initializes cleanly when both emulator hosts are None."""
    s = Settings(
        env="prod",
        firestore_emulator_host=None,
        firebase_auth_emulator_host=None,
    )
    assert s.env == "prod"
    assert s.firestore_emulator_host is None
    assert s.firebase_auth_emulator_host is None
