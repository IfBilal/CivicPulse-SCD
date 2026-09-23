"""`GET /api/meta/providers` — `04-CONTRACTS.md §6.6`. The ring entry carries exactly the
fields CLAUDE.md HARD rule 13 allows — never complaint text, a prompt, or a key."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import TriagedBy

ProviderName = Literal["llm", "ollama", "rules", "simulated"]  # values of TRIAGE_PROVIDER


class CacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float


class TriageOutcome(BaseModel):
    complaint_id: UUID
    provider: TriagedBy
    latency_ms: int
    fallback: bool
    cached: bool
    error_class: str | None = None
    at: datetime


class ProvidersOut(BaseModel):
    active: TriagedBy
    configured: ProviderName
    available: list[ProviderName]
    cache: CacheStats
    recent: list[TriageOutcome]  # newest first, ≤ RECENT_TRIAGE_MAX
