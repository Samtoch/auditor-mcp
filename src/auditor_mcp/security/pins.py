"""Pinning: a tool is only usable while its live definition matches the approved one.

Each tool has two definitions on record:

* ``approved`` - what a human reviewed and accepted.
* ``observed`` - what the server most recently advertised.

The tool is exposed to the model only when both fingerprints match. A new
tool has no approval yet, and a tool whose definition changes after approval
(a "rug pull") stops matching. Either way it is quarantined until someone
reviews it and runs ``auditor-gateway approve``.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from auditor_mcp.security.fingerprint import ToolDefinition, fingerprint


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PinStatus(StrEnum):
    APPROVED = "approved"  # observed definition matches the approved one
    NEW = "new"  # never approved
    CHANGED = "changed"  # approved once, but the definition has since changed
    REVOKED = "revoked"  # approval withdrawn by a human


@dataclass(slots=True)
class PinRecord:
    server: str
    tool: str
    observed_fingerprint: str
    observed_definition: ToolDefinition
    first_seen: str
    last_seen: str
    approved_fingerprint: str | None = None
    approved_definition: ToolDefinition | None = None
    approved_at: str | None = None
    revoked: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.server}/{self.tool}"

    @property
    def status(self) -> PinStatus:
        if self.revoked:
            return PinStatus.REVOKED
        if self.approved_fingerprint is None:
            return PinStatus.NEW
        if self.approved_fingerprint != self.observed_fingerprint:
            return PinStatus.CHANGED
        return PinStatus.APPROVED

    @property
    def is_trusted(self) -> bool:
        return self.status is PinStatus.APPROVED

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PinRecord:
        return cls(**data)


@dataclass(frozen=True, slots=True)
class Observation:
    """Result of comparing a live definition with the pin store."""

    record: PinRecord
    previous_status: PinStatus | None  # None if the tool was never seen before

    @property
    def status_changed(self) -> bool:
        return self.previous_status is not self.record.status


class PinStore:
    """Pin records persisted as one JSON file.

    Writes go to a temporary file followed by an atomic rename, so a crash
    can never leave a half-written pin file behind.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    # --- reading -----------------------------------------------------------

    def all(self) -> list[PinRecord]:
        with self._lock:
            return sorted(self._load().values(), key=lambda r: r.key)

    def get(self, server: str, tool: str) -> PinRecord | None:
        with self._lock:
            return self._load().get(f"{server}/{tool}")

    # --- writing -----------------------------------------------------------

    def observe(self, server: str, tool: str, definition: ToolDefinition) -> Observation:
        """Record what a server currently advertises for ``tool``."""
        fp = fingerprint(definition)
        now = _now()
        with self._lock:
            records = self._load()
            key = f"{server}/{tool}"
            record = records.get(key)
            if record is None:
                record = PinRecord(server, tool, fp, definition, first_seen=now, last_seen=now)
                records[key] = record
                self._save(records)
                return Observation(record, previous_status=None)

            previous = record.status
            record.last_seen = now
            if record.observed_fingerprint != fp:
                record.history.append(
                    {
                        "at": now,
                        "event": "definition_changed",
                        "from": record.observed_fingerprint,
                        "to": fp,
                    }
                )
                record.observed_fingerprint = fp
                record.observed_definition = definition
            self._save(records)
            return Observation(record, previous_status=previous)

    def approve(
        self, server: str, tool: str, *, expected_fingerprint: str | None = None
    ) -> PinRecord:
        """Approve the currently observed definition.

        ``expected_fingerprint`` guards against approving something other than
        what the reviewer looked at, if the definition changed in between.
        """
        with self._lock:
            records = self._load()
            record = self._require(records, server, tool)
            if expected_fingerprint and not record.observed_fingerprint.startswith(
                expected_fingerprint
            ):
                raise ValueError(
                    f"{record.key} changed since you reviewed it; "
                    "run 'show' again before approving."
                )
            now = _now()
            record.approved_fingerprint = record.observed_fingerprint
            record.approved_definition = record.observed_definition
            record.approved_at = now
            record.revoked = False
            record.history.append(
                {"at": now, "event": "approved", "fingerprint": record.approved_fingerprint}
            )
            self._save(records)
            return record

    def revoke(self, server: str, tool: str) -> PinRecord:
        with self._lock:
            records = self._load()
            record = self._require(records, server, tool)
            record.revoked = True
            record.history.append({"at": _now(), "event": "revoked"})
            self._save(records)
            return record

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _require(records: dict[str, PinRecord], server: str, tool: str) -> PinRecord:
        record = records.get(f"{server}/{tool}")
        if record is None:
            raise KeyError(
                f"No pin record for {server}/{tool}. Run 'auditor-gateway refresh' first."
            )
        return record

    def _load(self) -> dict[str, PinRecord]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {key: PinRecord.from_dict(value) for key, value in raw.get("tools", {}).items()}

    def _save(self, records: dict[str, PinRecord]) -> None:
        payload = {
            "version": 1,
            "tools": {key: asdict(record) for key, record in sorted(records.items())},
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self._path)
