"""Client settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ECHOKEY_API_URL: str = "http://localhost:8000"
    HOTKEY: str = "f12"


settings = Settings()
