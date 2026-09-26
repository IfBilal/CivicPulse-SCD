"""Regression test for the CI-only bug documented in docs/AI-USAGE.md (2026-09-26):
`alembic/env.py` called `fileConfig(config.config_file_name)` with no
`disable_existing_loggers` argument — stdlib's default for that argument is `True`, which
sets `.disabled = True` on every logger that already exists at call time and isn't named in
`alembic.ini`'s `[loggers]` section (only `root`, `sqlalchemy`, `alembic` are). `app.triage`
(`logging.getLogger("app.triage")`, created at `app/services/triage_service.py` import time)
is one of them.

`tests/integration/conftest.py::migrated_db` calls `command.upgrade(cfg, "head")` in-process
(not a subprocess) once per test session, which imports `alembic/env.py` and runs this exact
`fileConfig` call — permanently disabling `app.triage`'s logger for the rest of that pytest
process once the integration suite has run. This is exactly why three `caplog`-based
"exactly one WARNING" tests (`test_triage_service.py::test_exactly_one_warning_per_fallback`/
`test_no_extra_warning_on_retryable_then_fallback`, `test_logging_config.py::
test_fallback_emits_exactly_one_warning`) failed with `assert 0 == 1` only in CI's full,
unfiltered `pytest` run (contract + integration + unit together) and never in a narrower
local run that never executes `alembic upgrade head` — confirmed via a temporary diagnostic
print in CI showing `app.triage.disabled=True`.

Run as a subprocess (like `test_sigterm_drain.py`) rather than calling `fileConfig` directly
in this process: doing it in-process would either genuinely disable this test process's own
`app.triage` logger (repeating the exact bug for every test after it) or require restoring
`Logger.disabled` by hand, which is more fragile than just isolating it in its own process.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

_PROBE = textwrap.dedent(
    """
    import logging
    logging.getLogger("app.triage")  # simulate app/services/triage_service.py's module import
    from logging.config import fileConfig
    fileConfig("alembic.ini", disable_existing_loggers=False)
    print(logging.getLogger("app.triage").disabled)
    """
)


def test_alembic_file_config_does_not_disable_unrelated_loggers() -> None:
    result = subprocess.run(  # fixed argv, no shell, trusted fixed script text
        [sys.executable, "-c", _PROBE],
        cwd=_BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout.strip() == "False"
