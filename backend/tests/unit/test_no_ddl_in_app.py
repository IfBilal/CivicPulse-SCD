"""D3 — `05-DATA-LAYER.md §8`. `00-SPEC.md §2.3`: no `CREATE TABLE` in application startup
code, ever. A migration is versioned and reversible; a startup script is a hope."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_FORBIDDEN = re.compile(r"CREATE TABLE|CREATE TYPE|create_all")
_APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def test_no_ddl_in_app() -> None:
    offenders = []
    for path in _APP_ROOT.rglob("*.py"):
        text = path.read_text()
        if _FORBIDDEN.search(text):
            offenders.append(str(path))
    assert offenders == [], f"DDL found outside migrations: {offenders}"
