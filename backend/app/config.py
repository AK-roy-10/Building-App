"""Application configuration loaded from environment variables / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_secret: str = "dev-secret-change-me"

    database_url: str = "sqlite:///./trading.db"

    jwt_secret: str = "dev-jwt-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Fernet key (base64, 32-byte). If empty, a deterministic dev key is derived from app_secret.
    credential_enc_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
