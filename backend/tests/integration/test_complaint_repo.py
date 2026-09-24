"""D4-D10 — `05-DATA-LAYER.md §8`. Uses raw SQL where the point is proving the DATABASE enforces
an invariant, not just Pydantic — bypassing the ORM/repo on purpose for those cases."""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Category, Priority, Status, TriagedBy
from app.repositories.complaint_repo import ComplaintRepository

pytestmark = pytest.mark.integration


def _row(**overrides: object) -> dict[str, object]:
    base = {
        "id": uuid.uuid4(),
        "text": "Water main burst near the market, flooding the whole street badly.",
        "location": "Test Street 1",
        "reporter_contact": None,
        "category": Category.WATER,
        "priority": Priority.HIGH,
        "status": Status.OPEN,
        "ai_summary": "Water main burst.",
        "triaged_by": TriagedBy.RULES,
        "triage_latency_ms": 5,
        "triage_confidence": None,
    }
    base.update(overrides)
    return base


async def test_orm_enum_columns_round_trip_by_value(db_session: AsyncSession) -> None:
    """Regression: `PGEnum` without `values_callable` serialises a member by `.name`
    ("STREETLIGHTS"), which the DB's native enum type (lowercase-only, per migration 0001)
    rejects outright. Insert through the ORM/repo, then read the same row back with a raw
    query to confirm the DB actually stored the lowercase wire value, not just that the ORM
    round-trips it internally."""
    repo = ComplaintRepository(db_session)
    row = await repo.create(
        text="Streetlights on Main Road have been out for a week near the market gate.",
        location="Test Street 9",
        reporter_contact=None,
        category=Category.STREETLIGHTS,
        priority=Priority.NORMAL,
        ai_summary=None,
        triaged_by=TriagedBy.RULES,
        triage_latency_ms=1,
        triage_confidence=None,
    )
    await db_session.commit()

    raw = await db_session.execute(
        text("SELECT category::text, priority::text, status::text FROM complaints WHERE id = :id"),
        {"id": row.id},
    )
    category, priority, status = raw.one()
    assert category == "streetlights"
    assert priority == "normal"
    assert status == "open"


async def test_text_check_enforced_in_db(db_session: AsyncSession) -> None:
    """D4: raw INSERT with a 9-char text raises IntegrityError — proves the DB, not just
    Pydantic, enforces the bound."""
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO complaints (text, location, category, priority, triaged_by) "
                "VALUES ('too short', 'Some Location', 'water', 'high', 'rules')"
            )
        )
        await db_session.commit()


async def test_enum_rejects_unknown_category(db_session: AsyncSession) -> None:
    """D5: raw INSERT with an unknown enum value raises — the DB rejects a bad category even
    if the app layer is bypassed entirely."""
    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO complaints (text, location, category, priority, triaged_by) "
                "VALUES ('This text is definitely long enough to pass.', 'Some Location', "
                "'weather', 'high', 'rules')"
            )
        )
        await db_session.commit()


async def test_updated_at_trigger_fires(db_session: AsyncSession) -> None:
    """D6: a raw UPDATE (bypassing the ORM's `onupdate`, which doesn't exist here on purpose)
    still bumps `updated_at`, because the trigger is DB-enforced, not app-enforced.

    Uses `clock_timestamp()`, not `now()`, to force a distinguishable timestamp between the two
    inserts: `now()` is frozen to transaction-start time for the whole transaction it runs in,
    so two `now()` calls close together (as `commit()` on the same AsyncSession can produce) can
    resolve to the identical instant regardless of real wall-clock delay between them — which is
    exactly what made this test flake in CI. Forcing an explicit earlier timestamp via a raw
    UPDATE, then asserting the trigger overwrites it with something later, sidesteps the ambient
    transaction-timing question entirely.
    """
    repo = ComplaintRepository(db_session)
    row = await repo.create(
        text="Streetlight has been out for a week near the school gate area.",
        location="Test Street 2",
        reporter_contact=None,
        category=Category.STREETLIGHTS,
        priority=Priority.NORMAL,
        ai_summary=None,
        triaged_by=TriagedBy.RULES,
        triage_latency_ms=2,
        triage_confidence=None,
    )
    await db_session.commit()

    # Force updated_at into the past so the trigger's bump is unambiguously later, regardless
    # of how Postgres resolves now() inside the surrounding transaction.
    await db_session.execute(
        text("UPDATE complaints SET updated_at = now() - interval '1 hour' WHERE id = :id"),
        {"id": row.id},
    )
    await db_session.commit()
    before = (await repo.get(row.id)).updated_at  # type: ignore[union-attr]

    await db_session.execute(
        text("UPDATE complaints SET status = 'in_progress' WHERE id = :id"), {"id": row.id}
    )
    await db_session.commit()

    refreshed = await repo.get(row.id)
    assert refreshed is not None
    assert refreshed.updated_at > before


async def test_list_page_returns_total_in_one_query(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    await repo.bulk_seed([_row(id=uuid.uuid4()) for _ in range(3)])
    await db_session.commit()

    items, total = await repo.list_page(page=1, page_size=2)
    assert total == 3
    assert len(items) == 2


async def test_pagination_boundaries(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    await repo.bulk_seed([_row(id=uuid.uuid4())])
    await db_session.commit()

    items, total = await repo.list_page(page=1, page_size=1)
    assert total == 1
    assert len(items) == 1

    items, total = await repo.list_page(page=1, page_size=100)
    assert len(items) == 1  # PAGE_SIZE_MAX from domain/limits.py; upstream rejects >100


async def test_transition_conditional_update_is_atomic(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    row = await repo.create(
        text="Sewerage smell is very bad near the corner shop every evening now.",
        location="Test Street 3",
        reporter_contact=None,
        category=Category.SANITATION,
        priority=Priority.NORMAL,
        ai_summary=None,
        triaged_by=TriagedBy.RULES,
        triage_latency_ms=4,
        triage_confidence=None,
    )
    await db_session.commit()

    results = await asyncio.gather(
        repo.transition(row.id, Status.OPEN, Status.IN_PROGRESS),
        repo.transition(row.id, Status.OPEN, Status.REJECTED),
    )
    succeeded = [r for r in results if r is not None]
    assert len(succeeded) == 1  # exactly one of the two concurrent transitions wins


async def test_indexes_exist(db_session: AsyncSession) -> None:
    """D10: `pg_indexes` contains both named indexes — the actual Gate 2 checklist assertion,
    not just 'the model declares them'."""
    result = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'complaints'")
    )
    names = {row[0] for row in result.fetchall()}
    assert "ix_complaints_status_priority" in names
    assert "ix_complaints_created_at" in names
