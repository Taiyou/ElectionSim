from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./election_ai.db"

    # OpenRouter API (single key for all AI models)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Models via OpenRouter
    PERPLEXITY_MODEL: str = "perplexity/sonar-pro"
    GROK_MODEL: str = "x-ai/grok-3"
    CLAUDE_MODEL: str = "anthropic/claude-sonnet-4"

    # YouTube Data API v3
    YOUTUBE_API_KEY: str = ""

    # NewsAPI.org
    NEWS_API_KEY: str = ""

    # Pipeline Settings
    PARALLEL_PREFECTURES: int = 5
    SCHEDULE_HOURS: str = "8,12,20"
    API_RATE_LIMIT_PER_MINUTE: int = 30
    MAX_RETRIES: int = 3

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    @property
    def schedule_hours_list(self) -> list[int]:
        return [int(h.strip()) for h in self.SCHEDULE_HOURS.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {
        "env_file": [".env", "../.env"],
        "env_file_encoding": "utf-8",
    }


settings = Settings()
