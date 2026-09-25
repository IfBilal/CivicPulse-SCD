"""Runtime config, read once from env — `.env.example` is the source of truth for names.

`extra="forbid"` + `frozen=True`: a typo'd env var is a startup crash, not a silent
misconfiguration, and nothing can mutate config after boot (06-BACKEND-CORE.md §1).
"""

from typing import Literal

from pydantic import AnyHttpUrl, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid", frozen=True)

    app_env: Literal["dev", "prod"] = "dev"
    version: str = "dev"  # injected at build: ARG GIT_SHA
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@database:5432/civicpulse"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_s: int = 5

    redis_url: RedisDsn = RedisDsn("redis://cache:6379/0")

    triage_provider: Literal["llm", "ollama", "rules", "simulated"] = "simulated"
    triage_timeout_s: float = 10.0
    triage_total_budget_ms: int = 12_000
    triage_max_retries: int = 1
    triage_retry_jitter_ms: int = 250
    triage_cache_ttl_s: int = 86_400
    triage_min_confidence: float = 0.35
    triage_ring_size: int = 20

    # SimulatedTriage — deterministic fake, CI default.
    simulated_seed: int = 1337
    simulated_failure_mode: str = "none"

    llm_base_url: AnyHttpUrl = AnyHttpUrl("https://api.groq.com/openai/v1")
    llm_model: str = "openai/gpt-oss-20b"  # llama-3.1-8b-instant is retired on Groq's current
    # catalog — confirmed live 2026-09-25, see docs/TRIAGE.md §1
    llm_api_key: SecretStr = SecretStr("")  # SecretStr: never printed by repr()
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://ollama:11434")
    ollama_model: str = "llama3.2:1b"

    stats_cache_ttl_s: int = 30
    stats_cache_key: str = "stats:v1"
    ratelimit_enabled: bool = True
    ratelimit_requests: int = 10
    ratelimit_window_s: int = 60
    trusted_proxy_hops: int = 1

    cors_allow_origins: list[AnyHttpUrl] = []
    prestop_drain_s: float = 5.0

    @model_validator(mode="after")
    def _llm_needs_key(self) -> "Settings":
        if self.triage_provider == "llm" and not self.llm_api_key.get_secret_value():
            raise ValueError("TRIAGE_PROVIDER=llm requires LLM_API_KEY")
        return self


settings = Settings()
