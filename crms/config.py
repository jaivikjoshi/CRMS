"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://crms:crms_secret@localhost:5432/crms"
    api_key_hash_salt: str = "default_salt_change_in_prod"
    log_level: str = "INFO"


settings = Settings()
