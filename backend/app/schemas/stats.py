"""`GET /api/stats` — `04-CONTRACTS.md §6.5`. Every enum member appears as a key, even at 0."""

from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import Category, Priority, Status


class StatsOut(BaseModel):
    total: int
    by_category: dict[Category, int]
    by_priority: dict[Priority, int]
    by_status: dict[Status, int]
    generated_at: datetime
    cache_age_seconds: int | None  # 0 on a MISS
