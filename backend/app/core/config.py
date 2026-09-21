from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    service_name: str = "recover-ai-backend"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://recover_ai:recover_ai@localhost:5432/recover_ai"
    frontend_origin: str = "http://localhost:3000"
    llm_provider: str = "mock"
    llm_model: str = "recovery-recommendation"
    llm_api_key: str | None = None
    recovery_agent_mode: str = "mock"
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    razorpay_mode: str = "test"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
