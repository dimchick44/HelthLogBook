from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDARCHIVE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MedArchive API"
    environment: str = "dev"
    api_prefix: str = "/v1"

    database_url: str = "sqlite+aiosqlite:///./medarchive.db"
    auto_create_tables: bool = True

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    mail_domain: str = "in.medarchive.local"
    max_attachment_bytes: int = 25 * 1024 * 1024
    allowed_attachment_mimes: tuple[str, ...] = (
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/heic",
        "image/heif",
        "image/tiff",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    )

    storage_backend: str = "local"
    storage_root: str = "./.data"
    s3_endpoint: str | None = None
    s3_bucket: str = "medarchive"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "ru-central1"

    smtp_host: str = "127.0.0.1"
    smtp_port: int = 8025

    secret_encryption_key: str | None = None
    imap_sync_limit: int = 50
    imap_timeout_seconds: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
