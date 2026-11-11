"""Append-only security event log written by the gateway (never by the model)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class EventType(StrEnum):
    GATEWAY_STARTED = "gateway_started"
    SERVER_CONNECTED = "server_connected"
    SERVER_UNAVAILABLE = "server_unavailable"
    TOOL_NEW = "tool_new"  # first sighting; quarantined until approved
    TOOL_CHANGED = "tool_changed"  # definition differs from the approved one
    TOOL_RESTORED = "tool_restored"  # definition matches the approved one again
    TOOL_CALL_ALLOWED = "tool_call_allowed"
    TOOL_CALL_BLOCKED = "tool_call_blocked"
    TOOL_RESULT = "tool_result"
    TOOL_CALL_FAILED = "tool_call_failed"


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    event: EventType
    server: str | None = None
    tool: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event"] = self.event.value
        return {k: v for k, v in data.items() if v not in (None, {})}


class JsonlEventLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, event: GatewayEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False, default=str)
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._lock, self._path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
