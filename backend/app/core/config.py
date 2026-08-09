from __future__ import annotations

from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["local", "dev", "staging", "prod"] = "local"
    gcp_project_id: str = "activequeue-local"
    firestore_emulator_host: str | None = "localhost:8080"
    firebase_auth_emulator_host: str | None = "localhost:9099"
    content_provider: Literal["fixture", "youtube"] = "fixture"
    youtube_api_key: str | None = None
    max_items_per_source: int = 5000
    pages_per_chunk: int = 5
    sync_throttle_seconds: int = 900
    sync_stall_timeout_seconds: int = 3600
    full_walk_interval_days: int = 7
    auth_cache_ttl_seconds: int = 60
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    def model_post_init(self, __context: Any) -> None:
        """
        Asserts that emulators are not used in production.
        This is a critical security assertion: a leaked emulator host in production
        is a full auth bypass since emulators do not enforce authentication checks.
        """
        if self.env == "prod":
            assert self.firestore_emulator_host is None, (
                "Firestore emulator must not be enabled in production"
            )
            assert self.firebase_auth_emulator_host is None, (
                "Firebase Auth emulator must not be enabled in production"
            )


settings = Settings()
