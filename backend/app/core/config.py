"""
Centralized application configuration.
ALL secrets come from environment variables (.env locally, real env vars in
Docker/cloud). Nothing here is hardcoded. Never log this object directly —
use .safe_dict() if you need to log config state.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]  # Render: set to your static site's URL

    # --- Postgres (Render: paste the Internal Database URL it gives you) ---
    postgres_dsn: str = "postgresql+asyncpg://postgres:postgres@db:5432/trading"

    # --- Redis (Render: paste the Internal Redis URL it gives you) ---
    redis_url: str = "redis://redis:6379/0"

    # --- Twelve Data (Gold / XAU-USD) ---
    twelvedata_api_key: SecretStr = Field(default=SecretStr(""))

    # --- Binance (BTC/USD via BTC/USDT) ---
    binance_api_key: SecretStr = Field(default=SecretStr(""))
    binance_api_secret: SecretStr = Field(default=SecretStr(""))

    # --- News provider (Finnhub is now the sole source) ---
    finnhub_api_key: SecretStr = Field(default=SecretStr(""))

    # --- AI Decision Layer (provider-agnostic) ---
    llm_provider: Literal["claude", "openai"] = "openai"
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4.1"

    # --- Scheduler intervals (seconds) ---
    price_refresh_interval_sec: int = 30
    analysis_refresh_interval_sec: int = 120

    # --- Own API protection ---
    api_rate_limit: str = "60/minute"
    internal_api_key: SecretStr = Field(default=SecretStr(""))  # optional gate for your own API

    def safe_dict(self) -> dict:
        """Returns config with secrets redacted, for logging."""
        d = self.model_dump()
        for k, v in d.items():
            if "key" in k or "secret" in k or "dsn" in k:
                d[k] = "***redacted***"
        return d


@lru_cache
def get_settings() -> Settings:
    return Settings()
