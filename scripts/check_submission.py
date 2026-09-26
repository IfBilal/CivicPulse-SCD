#!/usr/bin/env python3
"""civicpulse submission check — mirrors 03-REPO-BOOTSTRAP.md §8.

Not a grader (§5.8). Encodes the eleven §5.3 deductions plus the mechanical
rubric lines as 18 checks. A check whose prerequisite files don't exist yet
(this repo builds phase by phase) prints SKIP, not FAIL — it becomes a real
gate automatically once that phase lands its files. Exit 0 unless a FAIL
fired; SKIP and WARN never block exit 0.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    check_id: str
    status: str  # PASS | FAIL | WARN | SKIP
    detail: str


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr=f"{cmd[0]}: not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr=f"{cmd[0]}: timed out")


def sec_env_history() -> Result:
    leaked = run(
        ["git", "log", "--all", "--diff-filter=A", "--name-only", "--", ".env", "*.pem", "*.key"]
    ).stdout.strip()
    if leaked:
        return Result("SEC-ENV-HISTORY", "FAIL", f"secret-shaped file added in history: {leaked}")
    gitleaks = run(["gitleaks", "detect", "--no-banner", "--redact", "--log-opts=--all", "-c", ".gitleaks.toml"])
    if gitleaks.returncode == 127:
        return Result("SEC-ENV-HISTORY", "WARN", "gitleaks not installed in this environment")
    if gitleaks.returncode not in (0, 1):
        return Result("SEC-ENV-HISTORY", "WARN", "gitleaks not runnable in this environment")
    if gitleaks.returncode == 1:
        return Result("SEC-ENV-HISTORY", "FAIL", "gitleaks found a secret in history")
    return Result("SEC-ENV-HISTORY", "PASS", "no secret in history")


def sec_k8s_secret() -> Result:
    k8s = ROOT / "k8s"
    if not k8s.exists():
        return Result("SEC-K8S-SECRET", "SKIP", "k8s/ does not exist yet (Phase 6b)")
    bad: list[str] = []
    # Values in the real manifests are YAML double-quoted strings (`"PLACEHOLDER_..."`), so the
    # placeholder check must strip a matched leading/trailing quote before testing. `DATABASE_URL`
    # specifically is a composite connection-string template with the placeholder marker
    # embedded in the userinfo section, not at the very start of the whole value — for that key,
    # judge only the `user:pass` userinfo segment (the only part that could actually carry a
    # credential), not the whole URL, which is legitimately long scaffolding
    # (`scheme://...@host:port/db`) even with a perfectly safe placeholder inside it (found via a
    # cold audit, 2026-09-26; see docs/AI-USAGE.md).
    placeholder_re = re.compile(r"^(PLACEHOLDER|CHANGE_ME)", re.IGNORECASE)
    for path in k8s.rglob("*secret*.y*ml"):
        text = path.read_text()
        for doc in text.split("\n---"):
            if "kind: Secret" not in doc:
                continue
            for line in doc.splitlines():
                m = re.match(r"\s*(\w+)\s*:\s*(.+)", line)
                if not m:
                    continue
                key, val = m.group(1), m.group(2).strip()
                if key in ("apiVersion", "kind", "metadata", "type", "data", "stringData", "name"):
                    continue
                unquoted = val[1:-1] if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'" else val
                if key == "DATABASE_URL":
                    userinfo_m = re.search(r"://([^@/]+)@", unquoted)
                    to_check = userinfo_m.group(1) if userinfo_m else unquoted
                else:
                    to_check = unquoted
                if len(to_check) >= 16 and not placeholder_re.match(to_check):
                    bad.append(f"{path.relative_to(ROOT)}: {key}")
    if bad:
        return Result("SEC-K8S-SECRET", "FAIL", f"non-placeholder value(s): {', '.join(bad)}")
    return Result("SEC-K8S-SECRET", "PASS", "all Secret manifests use placeholders")


def img_unpinned() -> Result:
    targets = list(ROOT.glob("**/Dockerfile")) + list(ROOT.glob("compose*.yaml")) + list((ROOT / "k8s").rglob("*.y*ml") if (ROOT / "k8s").exists() else [])
    targets = [t for t in targets if "node_modules" not in str(t) and "/.git/" not in str(t)]
    if not targets:
        return Result("IMG-UNPINNED", "SKIP", "no Dockerfile/compose/k8s manifests yet")
    bad: list[str] = []
    for path in targets:
        text = path.read_text()
        for m in re.finditer(r"^\s*FROM\s+(\S+)", text, re.MULTILINE):
            ref = m.group(1)
            if ":" not in ref.split("@")[0] or ref.endswith(":latest"):
                bad.append(f"{path.relative_to(ROOT)}: FROM {ref}")
        for m in re.finditer(r"image:\s*(\S+)", text):
            ref = m.group(1).strip("\"'")
            if ":" not in ref.split("@")[0] or ref.endswith(":latest"):
                bad.append(f"{path.relative_to(ROOT)}: image: {ref}")
    if bad:
        return Result("IMG-UNPINNED", "FAIL", "; ".join(bad))
    return Result("IMG-UNPINNED", "PASS", f"{len(targets)} manifest(s) all pinned")


def net_localhost() -> Result:
    # Brought into parity with `Makefile::lint-localhost`'s own already-established exclusions
    # (found via a cold audit, 2026-09-26, that this detector never picked up the same fixes —
    # see docs/AI-USAGE.md): a container healthcheck probes ITS OWN process on its own loopback
    # (not a service-to-service call, so not what CLAUDE.md §5.3's -8 is about); a comment line
    # explaining something isn't config; a dev-only ingress/overlay `host:`/`value: localhost`
    # (e.g. k8s/overlays/dev/ingress-host.yaml) is a deliberate local-access hostname, matching
    # `09-CACHE-RATELIMIT.md`/`14-LOAD-AUTOSCALING.md`'s own `civicpulse.localhost` examples.
    targets = [t for t in ("backend/app", "compose.yaml", "compose.prod.yaml", "k8s") if (ROOT / t).exists()]
    if not targets:
        return Result("NET-LOCALHOST", "SKIP", "no target paths exist yet")
    result = run(
        [
            "grep", "-rnI",
            "--exclude-dir=node_modules", "--exclude-dir=.git", "--exclude-dir=dist",
            "--exclude-dir=tests", "--exclude-dir=docs",
            "-e", "localhost", "-e", "127\\.0\\.0\\.1",
            *targets,
        ]
    )
    _comment_re = re.compile(r"^[^:]+:[0-9]+:\s*#")
    _host_value_re = re.compile(r'(host:|value:)\s*"?[A-Za-z0-9.-]*localhost')
    hits = [
        line
        for line in result.stdout.splitlines()
        if "healthcheck" not in line
        and not _comment_re.match(line)
        and not _host_value_re.search(line)
    ]
    if hits:
        return Result("NET-LOCALHOST", "FAIL", hits[0])
    checked = ", ".join(targets)
    missing = [t for t in ("backend/app", "compose.yaml", "compose.prod.yaml", "k8s") if t not in targets]
    note = f" ({', '.join(missing)} not created yet)" if missing else ""
    return Result("NET-LOCALHOST", "PASS", f"no localhost in {checked}{note}")


def net_segment() -> Result:
    compose = ROOT / "compose.yaml"
    if not compose.exists():
        return Result("NET-SEGMENT", "SKIP", "compose.yaml does not exist yet (Phase 5b)")
    text = compose.read_text()
    # The `internal:` network key and its own `internal: true` property aren't necessarily
    # adjacent lines (a real compose.yaml has `driver: bridge` between them, e.g.) — search the
    # whole `internal:` network block, not just the next line, for `internal: true` anywhere in
    # it (found via a cold audit, 2026-09-26, false-positiving a genuinely correct compose.yaml;
    # see docs/AI-USAGE.md).
    net_block_m = re.search(r"^  internal:\n((?:^ {4}.*\n)*)", text, re.MULTILINE)
    checks = {
        "internal network marked internal:true": bool(
            net_block_m and re.search(r"internal:\s*true", net_block_m.group(1))
        ),
        "frontend on edge only": "frontend" in text,
        "database on internal only": "database" in text,
    }
    missing = [k for k, ok in checks.items() if not ok]
    if missing:
        return Result("NET-SEGMENT", "FAIL", f"missing: {', '.join(missing)}")
    return Result("NET-SEGMENT", "PASS", "network segmentation present")


def port_exposed_prod() -> Result:
    prod = ROOT / "compose.prod.yaml"
    if not prod.exists():
        return Result("PORT-EXPOSED-PROD", "SKIP", "compose.prod.yaml does not exist yet (Phase 5b)")
    text = prod.read_text()
    bad = []
    for svc in ("database", "cache"):
        m = re.search(rf"^\s*{svc}:\n(?:.*\n)*?^\s*ports:", text, re.MULTILINE)
        if m:
            bad.append(svc)
    if bad:
        return Result("PORT-EXPOSED-PROD", "FAIL", f"ports: exposed for {', '.join(bad)} in compose.prod.yaml")
    return Result("PORT-EXPOSED-PROD", "PASS", "no db/cache ports published in prod")


def ci_needs() -> Result:
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return Result("CI-NEEDS", "SKIP", "ci.yml does not exist yet")
    text = ci.read_text()
    if "push: true" not in text and "kubectl apply" not in text and "helm upgrade" not in text and "docker/build-push-action" not in text:
        return Result("CI-NEEDS", "SKIP", "ci.yml is the Phase 0 placeholder, no publish/deploy steps yet")
    return Result("CI-NEEDS", "WARN", "publish/deploy step found — verify needs: manually, parser not built")


def cd_latest_deploy() -> Result:
    overlays = ROOT / "k8s" / "overlays"
    if not overlays.exists():
        return Result("CD-LATEST-DEPLOY", "SKIP", "k8s/overlays does not exist yet (Phase 6b)")
    bad = []
    for kustomization in overlays.rglob("kustomization.yaml"):
        result = run(["kubectl", "kustomize", str(kustomization.parent)])
        if result.returncode == 127:
            return Result("CD-LATEST-DEPLOY", "WARN", "kubectl not installed in this environment")
        if result.returncode != 0:
            return Result("CD-LATEST-DEPLOY", "WARN", "kubectl failed to render overlays")
        if ":latest" in result.stdout:
            bad.append(str(kustomization.parent.relative_to(ROOT)))
    if bad:
        return Result("CD-LATEST-DEPLOY", "FAIL", f":latest image in: {', '.join(bad)}")
    return Result("CD-LATEST-DEPLOY", "PASS", "no :latest in rendered overlays")


def k8s_db_deployment() -> Result:
    # `postgres-statefulset.yaml`, not `postgres.yaml` — the actual filename convention used
    # (self-describing: this file also holds the paired headless Service, `k8s/base/`'s own
    # pattern for every stateful component). Corrected 2026-09-26 via a cold audit; this check
    # was silently SKIPping forever against a file that was never going to exist under this
    # name (see docs/AI-USAGE.md).
    pg = ROOT / "k8s" / "base" / "postgres-statefulset.yaml"
    if not pg.exists():
        return Result(
            "K8S-DB-DEPLOYMENT", "SKIP", "k8s/base/postgres-statefulset.yaml does not exist yet"
        )
    text = pg.read_text()
    if "kind: StatefulSet" not in text:
        return Result("K8S-DB-DEPLOYMENT", "FAIL", "postgres.yaml is not a StatefulSet")
    if "volumeClaimTemplates" not in text:
        return Result("K8S-DB-DEPLOYMENT", "FAIL", "postgres StatefulSet has no volumeClaimTemplates")
    return Result("K8S-DB-DEPLOYMENT", "PASS", "postgres is a StatefulSet with volumeClaimTemplates")


def vcs_direct_main() -> Result:
    # GitHub squash-merge and merge-commit strategies both land on `main` as a single
    # commit with a single parent — `git log --no-merges` alone can't tell a squashed PR
    # apart from an actual direct push. A commit is treated as "came through a PR" if it's
    # either a real 2-parent merge, or its subject ends in GitHub's squash-merge suffix
    # `(#123)`. Only what's left after both allowances is a real direct-commit offender.
    result = run(["git", "log", "--first-parent", "main", "--format=%H %P||%s"])
    if result.returncode != 0:
        return Result("VCS-DIRECT-MAIN", "WARN", "could not read main history")
    offenders = []
    for line in result.stdout.splitlines():
        head, _, subject = line.partition("||")
        parts = head.split(" ", 1)
        commit_hash = parts[0]
        parents = parts[1].split() if len(parts) > 1 else []
        if len(parents) >= 2:
            continue  # real merge commit
        if re.search(r"\(#\d+\)\s*$", subject):
            continue  # GitHub squash-merge commit, came through a PR
        if re.match(r"^(all agents|all specs|assignment doc)", subject):
            continue  # initial scaffold commits, predate branch protection
        offenders.append(f"{commit_hash} {subject}")
    if offenders:
        return Result("VCS-DIRECT-MAIN", "FAIL", f"{len(offenders)} non-merge commit(s) on main after scaffold")
    return Result("VCS-DIRECT-MAIN", "PASS", "main has only the initial scaffold commits, rest are PR merges")


def doc_quickstart() -> Result:
    readme = ROOT / "README.md"
    if not readme.exists():
        # A missing README is the exact §5.3 −5 scenario this check exists to catch — SKIP
        # would silently under-report it as "nothing to check yet" instead of a real failure
        # (found via a cold audit, 2026-09-26; see docs/AI-USAGE.md).
        return Result("DOC-QUICKSTART", "FAIL", "root README.md does not exist (§5.3 −5)")
    text = readme.read_text()
    m = re.search(r"## Quickstart(.*?)(\n## |\Z)", text, re.DOTALL)
    if not m:
        return Result("DOC-QUICKSTART", "FAIL", "README.md has no ## Quickstart section")
    blocks = re.findall(r"```bash\n(.*?)```", m.group(1), re.DOTALL)
    if not blocks:
        return Result("DOC-QUICKSTART", "FAIL", "no fenced bash blocks under ## Quickstart")
    makefile_targets = set(re.findall(r"^([a-zA-Z_-]+):", (ROOT / "Makefile").read_text(), re.MULTILINE))
    missing = []
    for block in blocks:
        for line in block.strip().splitlines():
            cmd = line.strip().split()[0] if line.strip() else ""
            if cmd.startswith("make "):
                continue
            if cmd == "make":
                target = line.strip().split()[1] if len(line.strip().split()) > 1 else ""
                if target and target not in makefile_targets:
                    missing.append(f"make {target}")
    if missing:
        return Result("DOC-QUICKSTART", "FAIL", f"targets not in Makefile: {', '.join(missing)}")
    return Result("DOC-QUICKSTART", "PASS", "quickstart commands resolve against Makefile")


def env_parity() -> Result:
    # `settings.py`, not `config.py` — the actual filename this codebase uses throughout
    # (`app.settings.Settings`, imported as `from app.settings import settings` everywhere).
    # Corrected 2026-09-26 via a cold audit; this check was silently SKIPping forever against a
    # file that was never going to exist under this name (see docs/AI-USAGE.md).
    env_example = ROOT / ".env.example"
    config_py = ROOT / "backend" / "app" / "settings.py"
    if not env_example.exists():
        return Result("ENV-PARITY", "FAIL", ".env.example missing")
    if not config_py.exists():
        return Result("ENV-PARITY", "SKIP", "backend/app/settings.py does not exist yet")
    env_keys = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", env_example.read_text(), re.MULTILINE))
    config_keys = set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:", config_py.read_text(), re.MULTILINE))
    config_keys_upper = {k.upper() for k in config_keys}
    missing_in_config = env_keys - config_keys_upper
    missing_in_env = config_keys_upper - env_keys
    if missing_in_config or missing_in_env:
        return Result(
            "ENV-PARITY", "WARN",
            f"possible drift — in .env.example only: {sorted(missing_in_config)[:5]}, "
            f"in config.py only: {sorted(missing_in_env)[:5]}",
        )
    return Result("ENV-PARITY", "PASS", "env.example and config.py fields match")


def rubric_commits() -> Result:
    result = run(["git", "shortlog", "-sn", "--no-merges", "HEAD"])
    if result.returncode != 0 or not result.stdout.strip():
        return Result("RUBRIC-COMMITS", "WARN", "no shortlog output")
    rows = [line.split("\t") for line in result.stdout.strip().splitlines()]
    counts = [(int(n.strip()), name) for n, name in rows]
    total = sum(n for n, _ in counts)
    if total < 35:
        return Result("RUBRIC-COMMITS", "WARN", f"{total} commits total, floor is 35 (expected this early)")
    min_share = min(n / total for n, _ in counts) * 100
    if min_share < 35:
        return Result("RUBRIC-COMMITS", "WARN", f"min contributor share {min_share:.1f}% (floor 35%)")
    return Result("RUBRIC-COMMITS", "PASS", f"{total} commits, min share {min_share:.1f}%")


def rubric_prs() -> Result:
    result = run(["gh", "pr", "list", "--state", "merged", "--json", "number,reviews"])
    if result.returncode != 0:
        return Result("RUBRIC-PRS", "WARN", "gh not available or not authenticated")
    prs = json.loads(result.stdout)
    if len(prs) < 5:
        return Result("RUBRIC-PRS", "WARN", f"{len(prs)} merged PRs, floor is 5 (expected this early)")
    return Result("RUBRIC-PRS", "PASS", f"{len(prs)} merged PRs")


def rubric_tests() -> Result:
    backend_tests = ROOT / "backend" / "tests"
    frontend_tests = ROOT / "frontend" / "tests"
    if not backend_tests.exists() and not frontend_tests.exists():
        return Result("RUBRIC-TESTS", "SKIP", "no test directories yet")
    be_count = 0
    if backend_tests.exists():
        # Prefer the project's own venv interpreter over the caller's ambient `python3` — this
        # script isn't wired into CI (only `make submission-check`, a local dev target), and the
        # bare `python3 -m pytest` silently collected 0 tests whenever the caller's shell didn't
        # happen to have backend/.venv already activated (found via a cold audit, 2026-09-26,
        # reporting "0 backend tests collected" against a real 272-test suite — see
        # docs/AI-USAGE.md).
        venv_python = ROOT / "backend" / ".venv" / "bin" / "python3"
        python_bin = str(venv_python) if venv_python.exists() else "python3"
        result = run(
            [python_bin, "-m", "pytest", "--collect-only", "-q", "--no-cov"],
            cwd=ROOT / "backend",
        )
        # This project's own `-q --collect-only` output is file-level summary lines
        # (`path/to/test_x.py: 12`), not one `path::test_name` line per test — counting `"::"`
        # occurrences always undercounted to 0 against this specific format (found via a cold
        # audit, 2026-09-26; see docs/AI-USAGE.md). Sum the per-file counts instead. `--no-cov`
        # also added: the project's own `--cov-fail-under=65` addopts otherwise makes this
        # narrow collect-only invocation exit non-zero on an unrelated coverage floor.
        be_count = sum(int(n) for n in re.findall(r":\s*(\d+)\s*$", result.stdout, re.MULTILINE))
    if be_count < 14:
        return Result("RUBRIC-TESTS", "WARN" if backend_tests.exists() else "SKIP", f"{be_count} backend tests collected, floor is 14")
    return Result("RUBRIC-TESTS", "PASS", f"{be_count} backend tests collected")


def rubric_seed() -> Result:
    seed = ROOT / "backend" / "app" / "cli" / "seed.py"
    if not seed.exists():
        return Result("RUBRIC-SEED", "SKIP", "app/cli/seed.py does not exist yet (Phase 2)")
    return Result("RUBRIC-SEED", "SKIP", "requires a live DB — run via make seed, not this static check")


def rubric_adr() -> Result:
    adr_dir = ROOT / "docs" / "adr"
    expected = [
        "0001-provider-interface.md",
        "0002-frontend-runtime-config.md",
        "0003-deploy-by-sha.md",
        "0004-pii-and-data-governance.md",
    ]
    if not adr_dir.exists():
        return Result("RUBRIC-ADR", "SKIP", "docs/adr/ does not exist yet")
    missing = [f for f in expected if not (adr_dir / f).exists()]
    if missing:
        return Result("RUBRIC-ADR", "WARN", f"missing: {', '.join(missing)}")
    short = [f for f in expected if len((adr_dir / f).read_text().splitlines()) <= 40]
    if short:
        return Result("RUBRIC-ADR", "FAIL", f"under 40 lines: {', '.join(short)}")
    return Result("RUBRIC-ADR", "PASS", "all four ADRs present and substantial")


def rubric_evidence() -> Result:
    evidence_dir = ROOT / "docs" / "evidence"
    if not evidence_dir.exists():
        return Result("RUBRIC-EVIDENCE", "SKIP", "docs/evidence/ does not exist yet")
    manifest = [
        "branch-protection.png", "shortlog.txt", "merge-conflict-markers.txt",
        "merge-conflict-raw.py", "merge-conflict-graph.txt", "merge-conflict.md",
        "dockerignore-context-sizes.txt", "network-isolation.txt", "netpol-enforcement.txt",
        "persistence-compose.txt", "persistence-k8s.txt", "cache-behaviour.txt",
        "ratelimit-distributed.txt", "sigterm-drain.txt", "ci-red.png", "ci-green.png",
        "ci-gate-pr-url.txt", "hpa-watch.txt", "hpa-samples.txt", "hpa-replicas-vs-load.png",
        "k6-summary.json", "vpa-describe-run1.txt", "vpa-describe-run2.txt",
        "vpa-step1-guess.txt", "zero-downtime-rollout.txt", "provider-limits-groq.png",
        "alembic-history.txt", "explain-q-dash-filter.txt", "test-stability.txt",
        "runtime-config.txt",
    ]
    missing = [f for f in manifest if not (evidence_dir / f).exists() or (evidence_dir / f).stat().st_size == 0]
    if missing:
        return Result("RUBRIC-EVIDENCE", "WARN", f"{len(missing)}/{len(manifest)} evidence file(s) missing (expected this early)")
    return Result("RUBRIC-EVIDENCE", "PASS", "all evidence files present and non-empty")


CHECKS = [
    sec_env_history, sec_k8s_secret, img_unpinned, net_localhost, net_segment,
    port_exposed_prod, ci_needs, cd_latest_deploy, k8s_db_deployment,
    vcs_direct_main, doc_quickstart, env_parity, rubric_commits, rubric_prs,
    rubric_tests, rubric_seed, rubric_adr, rubric_evidence,
]

ICON = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}


def main() -> int:
    results = [check() for check in CHECKS]
    print(f"civicpulse submission check — {len(results)} checks")
    for r in results:
        print(f"  {ICON[r.status]:<5} {r.check_id:<22} {r.detail}")
    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARN"]
    skips = [r for r in results if r.status == "SKIP"]
    print(f"{len(fails)} FAIL, {len(warns)} WARN, {len(skips)} SKIP. Exit {1 if fails else 0}.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
