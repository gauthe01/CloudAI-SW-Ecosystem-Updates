from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    app_name: str = Field(
        default="Cloud AI Software Ecosystem Updates",
        alias="APP_NAME",
    )
    app_slug: str = Field(
        default="cloud-ai-software-ecosystem-updates",
        alias="APP_SLUG",
    )
    app_base_url: str = Field(default="http://localhost:3000", alias="APP_BASE_URL")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    enable_api_docs: bool = Field(default=True, alias="ENABLE_API_DOCS")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cloud_ai_software_ecosystem_updates",
        alias="DATABASE_URL",
    )
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")

    auth_mode: str = Field(default="local", alias="AUTH_MODE")
    app_secret_key: str = Field(default="local-development-change-me", alias="APP_SECRET_KEY")
    session_cookie_name: str = Field(
        default="cloud_ai_software_ecosystem_updates_session",
        alias="SESSION_COOKIE_NAME",
    )
    session_ttl_days: int = Field(default=30, alias="SESSION_TTL_DAYS")
    session_short_ttl_hours: int = Field(default=12, alias="SESSION_SHORT_TTL_HOURS")
    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")
    bootstrap_admin_email: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_display_name: str = Field(
        default="Local Admin",
        alias="BOOTSTRAP_ADMIN_DISPLAY_NAME",
    )
    local_user_default_password: str | None = Field(
        default=None,
        alias="LOCAL_USER_DEFAULT_PASSWORD",
    )

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: str = Field(
        default="cloud-ai-software-ecosystem-updates-local",
        alias="S3_BUCKET",
    )
    file_storage_backend: str = Field(default="local", alias="FILE_STORAGE_BACKEND")
    local_upload_storage_dir: str = Field(default="var/uploads", alias="LOCAL_UPLOAD_STORAGE_DIR")
    max_upload_size_mb: int = Field(default=25, alias="MAX_UPLOAD_SIZE_MB")

    ai_provider: str = Field(default="disabled", alias="AI_PROVIDER")
    ai_base_url: str | None = Field(default=None, alias="AI_BASE_URL")
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_model_update_extraction: str | None = Field(
        default=None,
        alias="AI_MODEL_UPDATE_EXTRACTION",
    )
    ai_model_reporting: str | None = Field(default=None, alias="AI_MODEL_REPORTING")
    ai_model_audio_transcription: str = Field(
        default="whisper-1",
        alias="AI_MODEL_AUDIO_TRANSCRIPTION",
    )
    ai_model_audio_speech: str = Field(default="tts-1", alias="AI_MODEL_AUDIO_SPEECH")
    ai_audio_voice: str = Field(default="alloy", alias="AI_AUDIO_VOICE")
    ai_timeout_seconds: float = Field(default=45.0, alias="AI_TIMEOUT_SECONDS")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")
    ai_ca_bundle: str | None = Field(default=None, alias="AI_CA_BUNDLE")
    ai_source_event_extraction_mode: str = Field(
        default="infrastructure_only",
        alias="AI_SOURCE_EVENT_EXTRACTION_MODE",
    )
    ai_source_event_max_output_tokens: int = Field(
        default=1200,
        alias="AI_SOURCE_EVENT_MAX_OUTPUT_TOKENS",
    )
    source_sync_enabled: bool = Field(default=True, alias="SOURCE_SYNC_ENABLED")
    source_sync_poll_seconds: float = Field(default=30.0, alias="SOURCE_SYNC_POLL_SECONDS")
    source_sync_interval_seconds: int = Field(
        default=300,
        alias="SOURCE_SYNC_INTERVAL_SECONDS",
    )
    source_sync_batch_size: int = Field(default=25, alias="SOURCE_SYNC_BATCH_SIZE")
    source_sync_initial_lookback_days: int = Field(
        default=365,
        alias="SOURCE_SYNC_INITIAL_LOOKBACK_DAYS",
    )
    source_sync_http_timeout_seconds: float = Field(
        default=30.0,
        alias="SOURCE_SYNC_HTTP_TIMEOUT_SECONDS",
    )
    rulebook_dir: str = Field(
        default="app/agents/rulebooks/content",
        alias="RULEBOOK_DIR",
    )

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def ai_enabled(self) -> bool:
        return self.ai_provider.strip().lower().replace("-", "_") not in {
            "",
            "disabled",
            "none",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
