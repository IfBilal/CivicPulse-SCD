"""`make seed` — idempotent, `05-DATA-LAYER.md §6`. Deterministic UUIDv5 ids mean re-running
this is a storage-layer no-op (`ON CONFLICT DO NOTHING`), not an application-layer `if exists`."""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db.seed_data import SEED_ROWS
from app.db.session import SessionLocal
from app.domain.enums import TriagedBy
from app.repositories.complaint_repo import ComplaintRepository

# Bump v1 -> v2 to intentionally mint a new seed generation (05-DATA-LAYER.md §6.1).
_SEED_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def _seed_id(text: str, location: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"civicpulse:seed:v1:{text}|{location}")


def _build_rows() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for text, location, contact, category, priority, status, day_offset, summary in SEED_ROWS:
        rows.append(
            {
                "id": _seed_id(text, location),
                "text": text,
                "location": location,
                "reporter_contact": contact,
                "category": category,
                "priority": priority,
                "status": status,
                "ai_summary": summary,
                "triaged_by": TriagedBy.RULES,
                "triage_latency_ms": 3,  # honest single-digit ms — this is rule-based, not an LLM
                "triage_confidence": None,
                "created_at": now - timedelta(days=day_offset, hours=day_offset % 5),
                "updated_at": now - timedelta(days=day_offset, hours=day_offset % 5),
            }
        )
    return rows


async def main() -> None:
    rows = _build_rows()
    async with SessionLocal() as session:
        repo = ComplaintRepository(session)
        try:
            await repo.bulk_seed(rows)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            sys.stderr.write(f"seed: insert failed, no rows committed this run: {exc}\n")
            raise
        total = await repo.count()
    sys.stdout.write(f"seed: {len(rows)} rows attempted, {total} rows now in complaints\n")


if __name__ == "__main__":
    asyncio.run(main())
