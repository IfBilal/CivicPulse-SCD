"""F22: `test_no_eval_or_exec_in_providers` — AST scan of `providers/` for `eval`/`exec`/
`compile` call nodes. §4.2 layer 5: never run model output through a code-evaluation builtin."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PROVIDERS_DIR = Path(__file__).resolve().parents[4] / "app" / "providers"
_FORBIDDEN_CALLS = {"eval", "exec", "compile"}


def _forbidden_calls_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        is_forbidden_call = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_CALLS
        )
        if is_forbidden_call:
            assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            found.append(f"{path}:{node.lineno} calls {node.func.id}()")
    return found


def test_no_eval_or_exec_in_providers() -> None:
    assert _PROVIDERS_DIR.is_dir(), f"expected {_PROVIDERS_DIR} to exist"
    py_files = list(_PROVIDERS_DIR.rglob("*.py"))
    assert py_files, "expected at least one provider source file"

    violations: list[str] = []
    for path in py_files:
        violations.extend(_forbidden_calls_in(path))

    assert violations == [], "forbidden call(s) found:\n" + "\n".join(violations)


def test_scan_is_falsifiable(tmp_path: Path) -> None:
    """CLAUDE.md HARD rule 14: confirm the AST scan WOULD catch a real violation. Writes a
    throwaway fixture file rather than embedding the forbidden builtin's call syntax directly
    in this test's own source."""
    banned_name = "".join(["e", "v", "a", "l"])  # built up to keep this file itself clean of it
    fixture = tmp_path / "bad_provider.py"
    fixture.write_text(f"def f(x):\n    return {banned_name}(x)\n", encoding="utf-8")
    found = _forbidden_calls_in(fixture)
    assert len(found) == 1
    assert banned_name in found[0]
