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
times per suite run. It was also a prime suspect for a separate, harder bug (see
`_no_disabled_loggers` below and `docs/AI-USAGE.md`, 2026-09-25/26) — ruled out once the
actual root cause (`alembic/env.py`'s `fileConfig` disabling `app.triage`'s logger) was
found and fixed directly, but this fix stands on its own regardless.
"""

import logging

import pytest

import app.main as main_module


@pytest.fixture(autouse=True, scope="session")
def _fast_prestop_drain() -> None:
    main_module.settings = main_module.settings.model_copy(update={"prestop_drain_s": 0.0})


@pytest.fixture(autouse=True)
def _no_disabled_loggers() -> None:
    """Guards against `Logger.disabled` leaking across tests regardless of collection order.

    Root cause found and fixed directly: `alembic/env.py`'s `fileConfig()` call defaulted
    `disable_existing_loggers` to `True`, which disabled `app.triage`'s logger the moment
    `tests/integration/conftest.py::migrated_db` ran a real `alembic upgrade head` in-process
    (confirmed via a live CI diagnostic — see `docs/AI-USAGE.md`, 2026-09-26). That fix closes
    the actual hole, but this fixture stays as defense-in-depth: it makes the guarantee
    unconditional and collection-order-independent instead of relying on exactly one call site
    never regressing (CLAUDE.md HARD rule 15: a flaky, order-dependent test is a design bug
    wearing a disguise)."""
    for logger_name in list(logging.root.manager.loggerDict):
        logging.getLogger(logger_name).disabled = False
    yield
