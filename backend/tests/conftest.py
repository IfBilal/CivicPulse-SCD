"""Session-wide test setup, shared by unit + contract + integration.

`prestop_drain_s` (`app/settings.py`) defaults to 5.0 — a real, production-correct
`asyncio.sleep()` the FastAPI `lifespan` runs on shutdown (`app/main.py`) so in-flight
requests survive a pod's SIGTERM before Redis/the triage provider/the DB pool close
(`06-BACKEND-CORE.md §6`). Every test file that builds a `TestClient(app)`/`create_app()`
(`test_cors.py`, `test_ready_route.py`, `test_meta_providers.py`,
`test_middleware_order.py`, `test_rate_limit_middleware.py`,
`test_request_id_middleware.py`, `test_unmatched_route_envelope.py`, both
`tests/contract/` files) runs that real 5-second sleep on teardown against the
production default, since none of them overrode it — confirmed via `pytest --durations`:
~13 teardowns at ~5.01s each, matching `prestop_drain_s` exactly. `test_sigterm_drain.py`
is the one test that already does this correctly, via a subprocess env var
(`PRESTOP_DRAIN_S=0.3`) — this fixture generalises that fix to every other in-process
`TestClient`, not just that one subprocess-based test.

This is a real CLAUDE.md HARD rule 15 violation ("never `time.sleep()` ... in a test") on
its own, independent of anything else — the async-sleep equivalent, run for real, ~13+
times per suite run. It was also the prime suspect for a separate, harder bug: three
`caplog`-based "exactly one WARNING" tests
(`tests/unit/services/test_triage_service.py::test_exactly_one_warning_per_fallback`/
`test_no_extra_warning_on_retryable_then_fallback`, `tests/unit/test_logging_config.py::
test_fallback_emits_exactly_one_warning`) failed with `assert 0 == 1` only in CI's full
297-test run (never locally, never in isolation) — the ~55-65s of real, blocking
`asyncio.sleep()` time these teardowns add is exactly the wall-clock gap observed between
CI's failure clusters. Patches `app.main.settings` (the name binding `lifespan()` actually
reads — `Settings` is frozen, and `app.main` does `from app.settings import settings` at
import time, so patching `app.settings.settings` after that import already happened
wouldn't reach it) rather than the `app.settings.settings` singleton itself, session-scoped
so it applies before any test module's own `TestClient`/`create_app()` fixture runs.
"""

import pytest

import app.main as main_module


@pytest.fixture(autouse=True, scope="session")
def _fast_prestop_drain() -> None:
    main_module.settings = main_module.settings.model_copy(update={"prestop_drain_s": 0.0})
