from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_default_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings default to local environment with emulator hosts set."""
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
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


_EMULATOR_VARS = ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST")


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_deployed_env_without_emulator_vars_talks_to_real_services(
    env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cloud Run sets ENV but no emulator variables (infra/modules/activequeue_app/main.tf).

    Regression: the emulator hosts used to default to localhost in every env, so dev and
    staging booted in auth-emulator mode (forged tokens accepted) and prod refused to boot.
    """
    for var in _EMULATOR_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ENV", env)

    s = Settings(_env_file=None)

    assert s.env == env
    assert s.firestore_emulator_host is None
    assert s.firebase_auth_emulator_host is None


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
@pytest.mark.parametrize(
    ("var", "message"),
    [
        ("FIRESTORE_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST must be UNSET"),
        ("FIREBASE_AUTH_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST must be UNSET"),
    ],
)
def test_deployed_env_refuses_to_start_pointed_at_an_emulator(
    env: str, var: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every internet-facing env refuses an emulator host, not just prod."""
    for other in _EMULATOR_VARS:
        monkeypatch.delenv(other, raising=False)
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv(var, "localhost:1234")

    with pytest.raises((ValueError, ValidationError), match=message):
        Settings(_env_file=None)


def test_local_env_defaults_to_the_dev_emulators(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (*_EMULATOR_VARS, "ENV"):
        monkeypatch.delenv(var, raising=False)

    s = Settings(_env_file=None)

    assert s.env == "local"
    assert s.firestore_emulator_host == "localhost:9090"
    assert s.firebase_auth_emulator_host == "localhost:9099"


def test_local_env_honours_an_explicit_none() -> None:
    s = Settings(env="local", firestore_emulator_host=None, firebase_auth_emulator_host=None)

    assert s.firestore_emulator_host is None
    assert s.firebase_auth_emulator_host is None


def test_prod_refuses_debug() -> None:
    with pytest.raises((ValueError, ValidationError), match="DEBUG must be false"):
        Settings(env="prod", debug=True)


@pytest.mark.parametrize("env", ["dev", "staging"])
def test_debug_is_allowed_in_non_prod_deployed_envs(env: str) -> None:
    assert Settings(env=env, debug=True).debug is True  # type: ignore[arg-type]
