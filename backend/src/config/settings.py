"""Central application settings loaded from .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/config/settings.py → backend/.env (cwd-independent)
_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — Claude is chat + wiki; OpenAI is Whisper/TTS
    openai_api_key: str = Field(..., description="OpenAI API key (Whisper / TTS)")
    openai_model_main: str = "gpt-4o"
    openai_model_cheap: str = "gpt-4o-mini"
    openai_transcribe_model: str = "whisper-1"
    openai_tts_model: str = "tts-1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # App
    # 0.0.0.0 so Tailscale-routed traffic can reach the server. Token-gated.
    app_host: str = "0.0.0.0"
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
    # Supabase project. The publishable key is the client key. Schema changes need the secret key.
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""

    # Knowledge
    tavily_api_key: str | None = None
    knowledge_rss_feeds: str = ""  # comma-separated override; blank uses config/feeds.yaml
    knowledge_feeds_config: Path = Path("config/feeds.yaml")
    knowledge_interests: str = "AI,engineering,science,business,design"  # comma-separated genres
    book_unofficial_links: bool = True  # Ocean of PDF search links when Gutenberg has no file

    # GitHub — used to personalize digest suggestions based on your projects
    github_username: str | None = None
    github_token: str | None = None  # optional; enables private repo access + higher rate limit
    github_vault_repo: str | None = None  # owner/name — write vault via Contents API
    github_vault_branch: str = "main"

    # Finance — Plaid
    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str = "sandbox"
    plaid_products: str = "transactions"
    plaid_country_codes: str = "US"
    # Fernet key for encrypting Plaid access tokens at rest
    plaid_token_encryption_key: str | None = None

    # Calendar — Google
    google_oauth_client_secrets: Path | None = None
    google_token_path: Path | None = None
    # Full token JSON for the cloud host. The Mac keeps using the token file.
    google_token_json: str = ""
    google_calendar_id: str = "primary"
    app_timezone: str = "America/New_York"

    # Health
    health_export_dir: Path | None = None
    usda_api_key: str | None = None

    # Apple Books MCP (local macOS Books app, read-only)
    apple_books_mcp_command: str = "uvx"
    apple_books_mcp_args: str = "apple-books-mcp@latest"

    @field_validator("openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _strip_secret_keys(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().strip("'").strip('"')

    @property
    def openai_key_present(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def openai_key_format_ok(self) -> bool:
        key = self.openai_api_key
        return key.startswith("sk-") and len(key) >= 40

    @property
    def anthropic_key_present(self) -> bool:
        return bool((self.anthropic_api_key or "").strip())

    @property
    def anthropic_key_format_ok(self) -> bool:
        key = (self.anthropic_api_key or "").strip()
        return key.startswith("sk-ant-") and len(key) >= 20

    @property
    def obsidian_base_url(self) -> str:
        return f"https://{self.obsidian_host}:{self.obsidian_port}"

    @property
    def rss_feed_list(self) -> list[str]:
        return [f.strip() for f in self.knowledge_rss_feeds.split(",") if f.strip()]

    @property
    def interest_list(self) -> list[str]:
        return [i.strip().lower() for i in self.knowledge_interests.split(",") if i.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
