"""Closed vocabularies — `04-CONTRACTS.md §1`. Frozen at Phase 1."""

from enum import StrEnum


class Category(StrEnum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class TriagedBy(StrEnum):
    LLM_GROQ = "llm:groq"  # §2.3 verbatim
    LLM_GEMINI = "llm:gemini"  # superset — contradiction A4
    LLM_OLLAMA = "llm:ollama"  # §2.3 verbatim
    RULES = "rules"  # §2.3 verbatim
    RULES_FALLBACK = "rules:fallback"  # §2.3 verbatim — THE value the fallback test asserts
    SIMULATED = "simulated"  # superset — contradiction A4, CI writes rows with it
