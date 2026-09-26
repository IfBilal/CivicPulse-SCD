"""`/health` and `/ready` — `04-CONTRACTS.md §6.7`, `§6.8`."""

from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok"]
    uptime_seconds: int
    version: str
    pid: int


class ReadyOut(BaseModel):
    status: Literal["ok"]
    checks: dict[str, str]  # {"postgres": "ok", "redis": "ok"}
