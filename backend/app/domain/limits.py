"""Field bounds — `04-CONTRACTS.md §2`. Imported by Pydantic schemas AND the Alembic migration,
so the app and DB CHECK constraints cannot drift. The frontend gets them via OpenAPI."""

TEXT_MIN = 10
TEXT_MAX = 2000
LOCATION_MIN = 3
LOCATION_MAX = 200
CONTACT_MAX = 120
SUMMARY_MAX = 140
NOTE_MAX = 280

PAGE_MIN = 1
PAGE_SIZE_MIN = 1
PAGE_SIZE_MAX = 100
PAGE_SIZE_DEFAULT = 20

RECENT_TRIAGE_MAX = 20  # §2.2: /api/meta/providers returns the last 20 outcomes
