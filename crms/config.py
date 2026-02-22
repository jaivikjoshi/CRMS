"""Application configuration."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://crms:crms_secret@localhost:5432/crms"

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        """Ensure postgresql+asyncpg scheme (Render gives postgresql://)."""
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    api_key_hash_salt: str = "default_salt_change_in_prod"
    log_level: str = "INFO"


settings = Settings()
