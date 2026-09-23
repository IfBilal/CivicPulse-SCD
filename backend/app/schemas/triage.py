"""`00-SPEC.md §2.5` verbatim. Not on the HTTP surface — this parses LLM output."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Category, Priority
from app.domain.limits import SUMMARY_MAX


class TriageResult(BaseModel):
    # extra="ignore": we don't control the model; an extra key must not force a fallback.
    # Contrast ComplaintCreate's extra="forbid" for clients we DO control (04-CONTRACTS §7).
    model_config = ConfigDict(extra="ignore")

    category: Category
    priority: Priority
    summary: str = Field(max_length=SUMMARY_MAX)
    confidence: float = Field(ge=0.0, le=1.0)
