"""`06-BACKEND-CORE.md §5`: `/health` must never import from `app.db` or `app.providers` at
module scope — a slow Postgres must fail READINESS, not LIVENESS (§5's wiring-backwards
failure: liveness checking the DB turns a DB stall into a cluster-wide restart loop).

This AST-scans `app/routes/ops.py` for module-level imports only. `/ready`'s DB/Redis checks
live in the SAME FILE but are imported lazily, inside the check functions, specifically so this
static guarantee holds for `/health` without splitting `/ready` into a separate module.
"""

import ast
import inspect

import pytest

from app.routes import ops

pytestmark = pytest.mark.unit

_FORBIDDEN_MODULE_PREFIXES = ("app.db", "app.providers", "app.repositories")


def _module_level_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in tree.body:  # tree.body is module-level only, not nested in functions
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_health_module_has_no_forbidden_module_level_imports() -> None:
    source = inspect.getsource(ops)
    imports = _module_level_imports(source)
    for forbidden in _FORBIDDEN_MODULE_PREFIXES:
        assert not any(name.startswith(forbidden) for name in imports), (
            f"app/routes/ops.py imports {forbidden!r} at module scope — /health would gain a "
            "DB/provider dependency, breaking the liveness/readiness distinction"
        )


def test_health_function_body_touches_no_db_or_provider_names() -> None:
    """Belt-and-braces: even a local import inside `health()` itself (not `_check_postgres`
    etc.) would be a regression. Scans only the `health` function's own AST subtree."""
    source = inspect.getsource(ops.health)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.AsyncFunctionDef)
    for node in ast.walk(func_def):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(_FORBIDDEN_MODULE_PREFIXES)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(_FORBIDDEN_MODULE_PREFIXES)
