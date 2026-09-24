"""Runtime config, read once from env — `.env.example` is the source of truth for names."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@database:5432/civicpulse"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_s: int = 5


settings = Settings()
