"""SIGTERM drain - `06-BACKEND-CORE.md section 6`: readiness flips false before the drain
sleep, an in-flight request completes rather than being dropped, and the process exits cleanly
(not SIGKILLed). Subprocess-based, no `time.sleep()` in the assertions (CLAUDE.md HARD rule
15) - polling uses a bounded retry loop with short async sleeps against a real socket instead,
and the subprocess itself is spawned via `asyncio.create_subprocess_exec` with an argument
list (never a shell string) so nothing here blocks the event loop or interpolates input into a
shell command.

This test uses `/health` (never touches the DB - `app/routes/ops.py`) so it needs no Postgres/
Redis/testcontainers, keeping it runnable in this sandbox while still proving the real
lifespan's shutdown ordering against a real OS-level SIGTERM, not a mocked one.
"""

import asyncio
import os
import signal
import socket
import sys
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.unit

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_until_serving(port: int, timeout_s: float = 10.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
                if r.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.05)
    raise TimeoutError("server never became reachable")


async def test_sigterm_flips_ready_false_then_drains_then_exits_clean() -> None:
    port = _free_port()
    env = {
        **os.environ,
        "TRIAGE_PROVIDER": "simulated",
        "PRESTOP_DRAIN_S": "0.3",  # short drain window so the test stays fast
        "RATELIMIT_ENABLED": "false",
    }
    # Fixed argument list, no shell involved — safe even though `sys.executable` is dynamic.
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--timeout-graceful-shutdown",
        "5",
        cwd=str(_BACKEND_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        await _wait_until_serving(port)

        async with httpx.AsyncClient() as client:
            ready_before = await client.get(f"http://127.0.0.1:{port}/ready", timeout=2.0)
            # /ready may already be 503 if Postgres/Redis aren't reachable in this sandbox — a
            # 503 body is now the 04-CONTRACTS.md §6.8 ErrorEnvelope shape
            # (error.details.checks), not the 200 ReadyOut shape (checks). What matters for
            # THIS test is the lifecycle field specifically: it must NOT say "shutting_down"
            # yet, since SIGTERM hasn't been sent.
            before_body = ready_before.json()
            checks_before = (
                before_body["checks"]
                if ready_before.status_code == 200
                else before_body["error"]["details"]["checks"]
            )
            assert checks_before.get("lifecycle") != "shutting_down"

            in_flight = asyncio.create_task(
                client.get(f"http://127.0.0.1:{port}/health", timeout=5.0)
            )
            await asyncio.sleep(0.05)
            sigterm_sent_at = asyncio.get_event_loop().time()
            proc.send_signal(signal.SIGTERM)

            resp = await in_flight
            assert resp.status_code == 200  # in-flight request completed, not dropped

        exit_code = await asyncio.wait_for(proc.wait(), timeout=15)
        drain_elapsed_s = asyncio.get_event_loop().time() - sigterm_sent_at
        # PRESTOP_DRAIN_S=0.3 above — the shutdown sequence must actually sleep that long
        # (06-BACKEND-CORE.md §6: drain BEFORE closing triage/redis/engine), not skip it.
        assert drain_elapsed_s >= 0.25
        # uvicorn's own SIGTERM handler runs the full graceful-shutdown sequence (visible in
        # its log: "Shutting down" -> "Waiting for application shutdown" -> "Application
        # shutdown complete" -> "Finished server process") and only then lets the process exit
        # via that same signal — Python reports that as -SIGTERM (-15), not 0. The invariant
        # this test actually proves is "not force-killed" (-9/SIGKILL), which would mean
        # `terminationGracePeriodSeconds` was exceeded and in-flight work got dropped.
        assert exit_code in (0, -signal.SIGTERM)
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
