"""`GET /api/stats` aggregation — `07-BACKEND-API.md §5`.

The Redis TTL cache / stampede lock (`X-Cache: HIT`, `cache_age_seconds`) is `09-CACHE-
RATELIMIT.md` scope, Phase 5. This phase wires the shape the route needs (`get()` returning
`(payload, hit, age)`, `invalidate()` as the write-path hook `ComplaintService.change_status`
already calls) with a pass-through implementation that always reports `MISS` / `age=0` — no
Redis dependency introduced early, no premature caching bug to debug before Phase 5 exists.
"""

from datetime import UTC, datetime

from app.domain.enums import Category, Priority, Status
from app.repositories.complaint_repo import ComplaintRepository
from app.schemas.stats import StatsOut


class StatsService:
    def __init__(self, repo: ComplaintRepository) -> None:
        self._repo = repo

    async def get(self) -> tuple[StatsOut, bool, int]:
        total, by_category, by_priority, by_status = await self._repo.stats_counts()
        payload = StatsOut(
            total=total,
            by_category={c: by_category.get(c, 0) for c in Category},
            by_priority={p: by_priority.get(p, 0) for p in Priority},
            by_status={s: by_status.get(s, 0) for s in Status},
            generated_at=datetime.now(UTC),
            cache_age_seconds=0,
        )
        return payload, False, 0

    async def invalidate(self) -> None:
        """No-op until Phase 5 adds the Redis cache key this would delete. Exists now so the
        write-path call site (`ComplaintService.change_status`) doesn't need to change shape
        when the real cache lands."""
        return None
