from __future__ import annotations

from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for application settings loaded via pydantic-settings.

    No module reads os.environ directly per SPEC §10.3.
    """

    env: Literal["local", "dev", "staging", "prod"] = "local"
    gcp_project_id: str = "demo-activequeue-local"
    firestore_emulator_host: str | None = "localhost:9090"
    firebase_auth_emulator_host: str | None = "localhost:9099"
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
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    def model_post_init(self, __context: Any) -> None:
        """Asserts that emulator hosts are completely UNSET when env == 'prod'.

        CRITICAL SECURITY ASSERTION (SPEC §10.3):
        - A leaked FIRESTORE_EMULATOR_HOST in production silently returns empty results
          instead of errors — a failure mode that looks like data loss.
        - A leaked FIREBASE_AUTH_EMULATOR_HOST in production causes Firebase Admin SDK
          to stop verifying signatures, accepting ANY forged token — a full auth bypass.
        """
        if self.env == "prod":
            if self.firestore_emulator_host is not None:
                msg = (
                    "CRITICAL SECURITY GUARDRAIL: FIRESTORE_EMULATOR_HOST must be UNSET "
                    "when env == 'prod'. Leaked emulator host causes silent data loss."
                )
                raise ValueError(msg)
            if self.firebase_auth_emulator_host is not None:
                msg = (
                    "CRITICAL SECURITY GUARDRAIL: FIREBASE_AUTH_EMULATOR_HOST must be UNSET "
                    "when env == 'prod'. Leaked emulator host allows full auth bypass."
                )
                raise ValueError(msg)


settings = Settings()
