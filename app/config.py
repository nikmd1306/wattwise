"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and validates application settings from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN"
    ADMIN_IDS: list[int] = []


settings = Settings()
