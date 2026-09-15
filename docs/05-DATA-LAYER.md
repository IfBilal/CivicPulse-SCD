# 05 — DATA LAYER (PostgreSQL 16 · SQLAlchemy 2.0 · Alembic)

> **Owner:** DEV-A · **Days:** 2 PM – 3 · **Gate:** Gate 2 · **Rubric:** D (12), part of C (4)
> **Hard rule from `00-SPEC.md §2.3`:** *no `CREATE TABLE` in application startup code, ever.*
> *A migration is a versioned, reviewable, reversible change; a startup script is a hope.*

---

## 1. Engine, session and pool

```python
# backend/app/db/session.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(
    settings.database_url,              # postgresql+psycopg://…  (psycopg 3, async)
    pool_size=settings.db_pool_size,        # 10
    max_overflow=settings.db_max_overflow,  # 5  → hard ceiling 15 per pod
    pool_timeout=settings.db_pool_timeout_s,# 5  → fail fast, do not queue behind a stall
    pool_pre_ping=True,                 # survives a Postgres restart / k8s pod delete
    pool_recycle=1800,
    echo=False,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
```

**Pool arithmetic that matters for Kubernetes.** `pool_size + max_overflow = 15` connections per
pod. HPA `maxReplicas: 10` ⇒ **150 connections**. Postgres 16 default `max_connections = 100`.
That is an outage waiting for the load test. Three defensible fixes, pick one and write it down:

1. Drop to `pool_size=5, max_overflow=2` ⇒ 70 at max replicas. **← default choice**
2. Raise `max_connections` in the StatefulSet's postgres config (costs memory per backend).
3. Introduce PgBouncer in transaction mode (correct at scale, extra component, extra marks-free complexity).

> This is a genuinely good `docs/ENGINEERING-NOTES.md` paragraph and a likely viva question:
> *"Your HPA can make ten pods. How many database connections is that?"*

`pool_pre_ping=True` is what makes Gate 6's *"delete the postgres pod, rows survive"* demo also
show the **application** surviving: the first checkout after the restart discovers the dead socket,
discards it, and opens a new one instead of surfacing a `ConnectionDoesNotExist` to a citizen.

---

## 2. ORM model

```python
# backend/app/db/models.py
from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
  "ix": "ix_%(table_name)s_%(column_0_N_name)s",
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)

category_enum = PGEnum(Category, name="category_enum", create_type=False, native_enum=True)
priority_enum = PGEnum(Priority, name="priority_enum", create_type=False, native_enum=True)
status_enum   = PGEnum(Status,   name="status_enum",   create_type=False, native_enum=True)
triaged_by_enum = PGEnum(TriagedBy, name="triaged_by_enum", create_type=False, native_enum=True)

class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                     server_default=text("gen_random_uuid()"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[Category] = mapped_column(category_enum, nullable=False)
    priority: Mapped[Priority] = mapped_column(priority_enum, nullable=False)
    status: Mapped[Status] = mapped_column(status_enum, nullable=False,
                                           server_default=text("'open'::status_enum"))
    ai_summary: Mapped[str | None] = mapped_column(String(140))
    triaged_by: Mapped[TriagedBy] = mapped_column(triaged_by_enum, nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    triage_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))   # contradiction A5
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                 server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                 server_default=text("now()"))
    __table_args__ = (
        CheckConstraint("char_length(text) BETWEEN 10 AND 2000",  name="text_len"),
        CheckConstraint("char_length(location) BETWEEN 3 AND 200", name="location_len"),
        CheckConstraint("reporter_contact IS NULL OR char_length(reporter_contact) BETWEEN 3 AND 120",
                        name="contact_len"),
        CheckConstraint("ai_summary IS NULL OR char_length(ai_summary) <= 140", name="summary_len"),
        CheckConstraint("triage_latency_ms >= 0", name="latency_nonneg"),
        CheckConstraint("triage_confidence IS NULL OR (triage_confidence >= 0 AND triage_confidence <= 1)",
                        name="confidence_range"),
        Index("ix_complaints_status_priority", "status", "priority"),
        Index("ix_complaints_created_at", text("created_at DESC")),
    )
```

### Decisions to be able to defend

| Decision | Why | Alternative rejected |
|---|---|---|
| `gen_random_uuid()` server-side | §2.3 says *"server-generated"*. Built into PG13+, **no `pgcrypto` extension needed on PG16** | client-side `uuid4()` — then the DB is not the authority and a replay could collide |
| `native_enum=True` (real PG types) | The DB rejects a bad category even if the app is bypassed — "enforced in the DB as well as the app" applied beyond `text` | `VARCHAR + CHECK` — easier to alter, weaker typing, and `\d+` shows nothing useful |
| `create_type=False` | The migration owns type creation; the ORM must not try to `CREATE TYPE` on first insert | letting SQLAlchemy autocreate — that is DDL at runtime, which §2.3 forbids in spirit |
| `TIMESTAMP(timezone=True)` | §2.3: `timestamptz`, UTC. PG stores UTC and converts on read | `timestamp` — loses the offset and makes an Islamabad/UTC bug inevitable |
| `Numeric(3,2)` for confidence | exact, comparable, no float drift in a `WHERE confidence < 0.35` | `REAL` |
| No `ON DELETE` / no FKs | single-table schema; nothing to cascade | — |

---

## 3. Alembic

### 3.1 `alembic/env.py` essentials

```python
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    compare_type=True,              # catches VARCHAR(120)→VARCHAR(200)
    compare_server_default=True,    # catches a changed DEFAULT
    include_schemas=False,
    render_as_batch=False,          # Postgres does not need batch mode; SQLite would
)
```
URL comes from `settings.database_url`, **not** from `alembic.ini` — so the same migration runs
against compose, CI and Kubernetes with no file edits. `alembic.ini` keeps only
`script_location` and the file template:

```ini
file_template = %%(rev)s_%%(slug)s
```

### 3.2 Migration `0001_initial.py` — the DDL, written by hand

Autogenerate does **not** get native enums, `DESC` indexes or triggers right. Write it, then verify
with `alembic revision --autogenerate` producing an **empty** diff.

```python
def upgrade() -> None:
    op.execute("CREATE TYPE category_enum AS ENUM "
               "('water','electricity','sanitation','roads','streetlights','other')")
    op.execute("CREATE TYPE priority_enum AS ENUM ('high','normal','low')")
    op.execute("CREATE TYPE status_enum AS ENUM ('open','in_progress','resolved','rejected')")
    op.execute("CREATE TYPE triaged_by_enum AS ENUM "
               "('llm:groq','llm:gemini','llm:ollama','rules','rules:fallback','simulated')")

    op.create_table("complaints", ...)          # columns exactly as §2 above
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    op.execute("CREATE INDEX ix_complaints_created_at ON complaints (created_at DESC)")

    op.execute("""
    CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
    BEGIN NEW.updated_at = now(); RETURN NEW; END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_complaints_updated_at BEFORE UPDATE ON complaints
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_complaints_updated_at ON complaints")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    for t in ("triaged_by_enum","status_enum","priority_enum","category_enum"):
        op.execute(f"DROP TYPE IF EXISTS {t}")
```

**The `updated_at` trigger, not `onupdate=func.now()`.** A Python-side `onupdate` only fires for
ORM-issued UPDATEs. The trigger fires for the seed script, for a `psql` hotfix, and for the
conditional status UPDATE in `04-CONTRACTS.md §6.4`. *DB-enforced invariants belong in the DB* —
same argument as the `text` length CHECK, and worth one sentence in the notes.

**`DROP TYPE` in `downgrade`.** Forgetting it is the classic bug: `downgrade` then `upgrade` fails
with `type "category_enum" already exists`. Gate 2 tests exactly this round trip.

### 3.3 Migration hygiene rules

| Rule | Reason |
|---|---|
| One migration per PR, max | Two heads on a merge (`01-WORKFLOW.md §3.3`) |
| Every `upgrade` has a real `downgrade` | §2.3: *"reversible"*. `pass` is not reversible. |
| Never edit an applied migration | Partner's DB is already at that revision |
| Data migrations separate from schema migrations | A failed backfill should not roll back a column add |
| `alembic upgrade head` runs in `make up` and in the k8s **initContainer**, never in `main.py` | Rubric D's 4-mark line |

**Where migrations run on Kubernetes:** an `initContainer` on the backend Deployment running
`alembic upgrade head`. Not a Job (a Job and a rolling update race), not `main.py` (that is startup
DDL). Two replicas both running the initContainer is safe — Alembic takes an advisory lock on
`alembic_version`; the loser waits and then sees `head` already applied. Verify this once and
write it down; it is a strong viva answer.

---

## 4. Indexes — each justified by a named query (Rubric D, 2 marks)

> *An unexplained index is cargo cult* (§2.3).

### `ix_complaints_status_priority` — serves `Q-DASH-FILTER`

```sql
-- Q-DASH-FILTER: the Dashboard's default operator view
SELECT c.*, COUNT(*) OVER () AS total_count
FROM complaints c
WHERE c.status = 'open' AND c.priority = 'high'
ORDER BY c.created_at DESC
LIMIT 20 OFFSET 0;
```
Leading column `status` is the highest-selectivity predicate an operator actually uses (they live in
`status='open'`). `priority` second so `WHERE status=? AND priority=?` is a single index range scan,
and `WHERE status=?` alone still uses the index prefix. The reverse order would leave the common
status-only query unable to use the leading column.

Evidence to commit: `docs/evidence/explain-q-dash-filter.txt` containing `EXPLAIN (ANALYZE, BUFFERS)`
**before and after** the index, against the seeded table. *Seq Scan → Bitmap Index Scan* is the line
you point at in the viva.

### `ix_complaints_created_at (DESC)` — serves `Q-LIST-RECENT`

```sql
-- Q-LIST-RECENT: unfiltered dashboard page 1 and the stats time window
SELECT * FROM complaints ORDER BY created_at DESC LIMIT 20;
```
`DESC` in the index definition means the planner can walk the index forward and stop at 20 with
no sort node. Ascending would also work (PG can scan backwards) but the explicit `DESC` makes
the intent legible and matches a future `(created_at DESC, id DESC)` tiebreaker.

**Known gap, disclose it:** neither index helps deep `OFFSET`. `OFFSET 5000` still walks 5000
rows. At this data volume it is irrelevant; the honest answer is *keyset pagination*
(`WHERE (created_at, id) < (:last_created, :last_id)`), rejected here because §2.2 mandates a
`page`/`page_size`/`total` envelope. Put that trade-off in the notes — knowing why you did the
worse thing is worth more than doing the better thing silently.

---

## 5. Repository layer — **all SQL lives here** (Rubric C, 4 marks)

```python
# backend/app/repositories/complaint_repo.py
class ComplaintRepository:
    def __init__(self, session: AsyncSession) -> None: self._s = session

    async def create(self, *, text, location, contact, triage, latency_ms) -> Complaint: ...
    async def get(self, cid: UUID) -> Complaint | None: ...
    async def list_page(self, *, categories, priorities, statuses, page, page_size, sort
                        ) -> tuple[Sequence[Complaint], int]: ...
    async def transition(self, cid: UUID, expected: Status, new: Status) -> Complaint | None: ...
```

`list_page` issues **one** statement:

```python
total_col = func.count().over().label("total_count")
stmt = select(Complaint, total_col)
if statuses:   stmt = stmt.where(Complaint.status.in_(statuses))
if priorities: stmt = stmt.where(Complaint.priority.in_(priorities))
if categories: stmt = stmt.where(Complaint.category.in_(categories))
stmt = stmt.order_by(ORDERINGS[sort]).limit(page_size).offset((page - 1) * page_size)
rows = (await self._s.execute(stmt)).all()
total = rows[0].total_count if rows else 0
```

`transition` is the conditional UPDATE from `04-CONTRACTS.md §6.4`:

```python
stmt = (update(Complaint)
        .where(Complaint.id == cid, Complaint.status == expected)
        .values(status=new)
        .returning(Complaint))
res = (await self._s.execute(stmt)).scalar_one_or_none()   # None ⇒ caller raises 409
```

**Enforcement of the layer boundary** (this is a marked line, so automate it):

```makefile
lint-layers:
	@! grep -rnE "select\(|session|execute\(|text\(" backend/app/routes/ || (echo "SQL in routes"; exit 1)
	@! grep -rnE "HTTPException|status_code|Response" backend/app/repositories/ backend/app/services/ \
	   || (echo "HTTP concerns below routes"; exit 1)
	@! grep -rn "from app.routes" backend/app/services backend/app/repositories backend/app/providers \
	   || (echo "upward import — arrows point one way"; exit 1)
```

Wire `lint-layers` into `make check` and into the CI `lint-and-type` job. *A route that opens a
database session is a design failure worth marks* (§2.2) — so make it impossible to merge one.

---

## 6. The idempotent seed (Rubric D, 3 marks)

**Requirement:** ≥ 30 realistic complaints in Urdu-influenced English, spread across categories,
**running it twice must not duplicate rows** (§2.3).

### 6.1 The idempotency mechanism — deterministic UUIDv5

No extra column, no extra unique constraint, no `DELETE` before insert:

```python
SEED_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

def seed_id(item: dict) -> uuid.UUID:
    return uuid.uuid5(SEED_NS, f"civicpulse:seed:v1:{item['text']}|{item['location']}")

stmt = pg_insert(Complaint).values(rows).on_conflict_do_nothing(index_elements=["id"])
```

The primary key already has a unique index, so `ON CONFLICT (id) DO NOTHING` needs nothing
new. Re-running is a no-op at the storage layer, not at the application layer — which is the
difference between *idempotent* and *has an if-statement*.

Bump `v1` → `v2` in the namespace string to intentionally introduce a new seed generation.

### 6.2 Seed data rules

- **≥ 30 rows**, ship 36 so the count survives an edit.
- **Spread across all six categories** — assert in the test that every category has ≥ 3 rows and
  every priority has ≥ 5, otherwise the Stats chart demos an empty bucket.
- **Spread `created_at` across ~14 days** (`now() - (random interval)`) so `ix_complaints_created_at`
  has something to sort and the dashboard does not show 36 identical timestamps.
- **Spread `status`** so the transition demo has an `in_progress` row to resolve on camera.
- **`triaged_by` set to `rules`** for seed rows, with honest `triage_latency_ms` (single-digit ms).
  Do **not** fabricate `llm:groq` rows — `/api/meta/providers` would then lie, and lying telemetry
  is worse than no telemetry.
- **Urdu-influenced English**, register-accurate, e.g.:
  - *"Since fajr the water is coming out from main line near Street 12, ground floor is full, kindly send team urgent."*
  - *"Light of pole number 14 is fused from three days, at night it is total dark, ladies are afraid to walk."*
  - *"Sewerage water standing in front of my gate since last Monday, smell is very bad, children are getting sick."*
  - *"Bijli is going every one hour in G-9 sector from morning, transformer is making loud noise."*
  - *"Road is broken near the chowk, big khudda there, one bike already fell yesterday."*
- **No real PII.** Invented names, invented numbers in a documented test range. This is the same
  governance argument as ADR-0004 applied to your own fixtures.

### 6.3 Seed acceptance tests

| Test | Assertion |
|---|---|
| `test_seed_is_idempotent` | run twice against a fresh DB ⇒ `count()` equal, and equal to `len(SEED_DATA)` |
| `test_seed_minimum_volume` | `count() >= 30` |
| `test_seed_category_spread` | every `Category` member has ≥ 3 rows |
| `test_seed_priority_spread` | every `Priority` member has ≥ 5 rows |
| `test_seed_respects_constraints` | no row violates any CHECK (implicitly true, but asserts the fixtures were not written past the limits) |
| `test_seed_ids_are_stable` | the UUID of row 0 equals a committed golden value — proves determinism across machines |

---

## 7. Persistence contract — both demonstrations (§2.3)

### 7.1 Compose

```bash
make up && make seed
docker compose exec -T database psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc \
  'select count(*) from complaints' | tee docs/evidence/persistence-compose.txt
docker compose down                       # NOT -v
docker compose up -d --wait
docker compose exec -T database psql ... -tAc 'select count(*) from complaints' \
  | tee -a docs/evidence/persistence-compose.txt
# the two numbers must match
```

The failure mode to avoid: mounting the volume at `/var/lib/postgresql` instead of
`/var/lib/postgresql/data`. It *looks* right, `down`/`up` *appears* to work on the first try because
the container was never removed, and the data vanishes the first time an image tag changes.

### 7.2 Kubernetes

```bash
kubectl -n civicpulse exec postgres-0 -- psql -U civicpulse -tAc 'select count(*) from complaints'
kubectl -n civicpulse delete pod postgres-0
kubectl -n civicpulse wait --for=condition=ready pod/postgres-0 --timeout=180s
kubectl -n civicpulse exec postgres-0 -- psql -U civicpulse -tAc 'select count(*) from complaints'
```
Tee both into `docs/evidence/persistence-k8s.txt`. This is the demonstration that makes
*"A Deployment for a database is a marked error"* (§3.3) concrete: the StatefulSet's
`volumeClaimTemplates` re-binds the **same** PVC to the replacement pod by ordinal name
(`pgdata-postgres-0`), which a Deployment's pod template cannot guarantee.

---

## 8. Test matrix for this layer (contributes to Rubric C's ≥ 14)

| # | Test | Type | Asserts |
|---|---|---|---|
| D1 | `test_migration_round_trip` | integration | `upgrade head` → `downgrade base` → `upgrade head` clean, including `DROP TYPE` |
| D2 | `test_autogenerate_is_empty` | integration | `alembic revision --autogenerate` produces no ops ⇒ model and migration agree |
| D3 | `test_no_ddl_in_app` | unit | `grep` for `CREATE TABLE\|CREATE TYPE\|create_all` under `app/` returns nothing |
| D4 | `test_text_check_enforced_in_db` | integration | raw `INSERT` with a 9-char text raises `IntegrityError` — proves the DB, not just Pydantic |
| D5 | `test_enum_rejects_unknown_category` | integration | raw `INSERT … 'weather'` raises `InvalidTextRepresentation` |
| D6 | `test_updated_at_trigger_fires` | integration | raw `UPDATE` (bypassing ORM) bumps `updated_at` |
| D7 | `test_list_page_returns_total_in_one_query` | integration | assert exactly one statement via an `after_cursor_execute` counter |
| D8 | `test_pagination_boundaries` | integration | `page_size` 1 / 100 ok, 0 / 101 rejected upstream |
| D9 | `test_transition_conditional_update_is_atomic` | integration | two concurrent `transition()` calls ⇒ one returns a row, one returns `None` |
| D10 | `test_indexes_exist` | integration | `pg_indexes` contains both index names |
| D11 | `test_seed_*` (×6) | integration | §6.3 |

Integration tests use **testcontainers** (`postgres:16-alpine`, pinned) so they run identically on a
laptop and on a CI runner — which is, literally, §5.2 question 1.
