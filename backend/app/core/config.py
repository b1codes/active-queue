from __future__ import annotations

from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_FIRESTORE_EMULATOR_HOST = "localhost:9090"
LOCAL_AUTH_EMULATOR_HOST = "localhost:9099"


class Settings(BaseSettings):
    """Single source of truth for application settings loaded via pydantic-settings.

    No module reads os.environ directly per SPEC §10.3.
    """

    env: Literal["local", "dev", "staging", "prod"] = "local"
    gcp_project_id: str = "demo-activequeue-local"
    # Emulator hosts default to the dev emulators only when env == "local" (see
    # model_post_init). Every deployed env defaults to None, so a Cloud Run service that
    # sets ENV but no emulator variables talks to real Firestore and verifies signatures.
    firestore_emulator_host: str | None = None
    firebase_auth_emulator_host: str | None = None
    content_provider: Literal["fixture", "youtube"] = "fixture"
    youtube_api_key: str | None = None
    max_items_per_source: int = 5000
    pages_per_chunk: int = 5
    sync_throttle_seconds: int = 900
    sync_stall_timeout_seconds: int = 3600
    full_walk_interval_days: int = 7
    auth_cache_ttl_seconds: int = 60
    rate_limit_general: int = 60
    rate_limit_sync: int = 10
    rate_limit_heavy: int = 30
    rate_limit_window_seconds: int = 60
    # Per-IP flood guard, applied before any token work. Generous because carrier-grade
    # NAT puts many legitimate users behind one address; per-user limits do the real work.
    rate_limit_ip: int = 300
    # How many proxies in front of the app append to X-Forwarded-For. Cloud Run's front
    # end appends the caller's address, so 1 there; 0 locally (use the TCP peer).
    trusted_proxy_hops: int = 0
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    def model_post_init(self, __context: Any) -> None:
        """Default the emulator hosts for local dev, and refuse them in any deployed env.

        CRITICAL SECURITY ASSERTION (SPEC §10.3):
        - A leaked FIRESTORE_EMULATOR_HOST silently returns empty results instead of
          errors, a failure mode that looks like data loss.
        - A leaked FIREBASE_AUTH_EMULATOR_HOST makes the Firebase Admin SDK stop
          verifying signatures, so ANY forged token is accepted: a full auth bypass.

        dev, staging and prod are all internet-facing Cloud Run services, so the
        assertion covers every env except "local". The localhost defaults apply only
        when env == "local" and the host was not passed explicitly (an explicit None
        keeps the emulator off).
        """
        if self.env == "local":
            if "firestore_emulator_host" not in self.model_fields_set:
                self.firestore_emulator_host = LOCAL_FIRESTORE_EMULATOR_HOST
            if "firebase_auth_emulator_host" not in self.model_fields_set:
                self.firebase_auth_emulator_host = LOCAL_AUTH_EMULATOR_HOST
            return

        if self.env == "prod" and self.debug:
            msg = "DEBUG must be false when env == 'prod' (verbose console logs, DEBUG level)."
            raise ValueError(msg)
        if self.firestore_emulator_host is not None:
            msg = (
                "CRITICAL SECURITY GUARDRAIL: FIRESTORE_EMULATOR_HOST must be UNSET "
                f"when env == '{self.env}'. Leaked emulator host causes silent data loss."
            )
            raise ValueError(msg)
        if self.firebase_auth_emulator_host is not None:
            msg = (
                "CRITICAL SECURITY GUARDRAIL: FIREBASE_AUTH_EMULATOR_HOST must be UNSET "
                f"when env == '{self.env}'. Leaked emulator host allows full auth bypass."
            )
            raise ValueError(msg)


settings = Settings()
