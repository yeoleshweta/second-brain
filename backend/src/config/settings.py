"""Central application settings loaded from .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model_main: str = "gpt-4o"
    openai_model_cheap: str = "gpt-4o-mini"

    # App
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"
    environment: str = "development"
    app_api_token: str = "change-me"

    # Obsidian
    obsidian_api_key: str | None = None
    obsidian_host: str = "127.0.0.1"
    obsidian_port: int = 27124
    obsidian_vault_path: Path | None = None

    # Storage
    database_url: str = "sqlite:///./data/secondbrain.db"
    data_dir: Path = Path("./data")

    # Knowledge
    tavily_api_key: str | None = None
    knowledge_rss_feeds: str = ""  # comma-separated

    # Finance — Plaid
    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str = "sandbox"
    plaid_products: str = "transactions"
    plaid_country_codes: str = "US"

    # Calendar — Google
    google_oauth_client_secrets: Path | None = None
    google_token_path: Path | None = None
    google_calendar_id: str = "primary"

    # Health
    health_export_dir: Path | None = None
    usda_api_key: str | None = None

    @property
    def obsidian_base_url(self) -> str:
        return f"https://{self.obsidian_host}:{self.obsidian_port}"

    @property
    def rss_feed_list(self) -> list[str]:
        return [f.strip() for f in self.knowledge_rss_feeds.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
