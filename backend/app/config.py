"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    app_name: str = "Dynasty Edge API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Neo4j Production (Railway)
    neo4j_url: str = "https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "dynastyedge2025"

    # Supabase (Auth)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_jwt_secret: str = ""

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://dynastyedge.pages.dev",
        "https://*.dynastyedge.pages.dev",
        "https://frontend-iota-swart-17.vercel.app",
        "https://*.vercel.app",
    ]

    # Rate Limits (per minute)
    rate_limit_free: int = 10
    rate_limit_pro: int = 100
    rate_limit_elite: int = 1000

    # Freemium Tier Limits
    free_trade_limit_daily: int = 3
    free_rankings_limit: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Cache settings for performance."""
    return Settings()
