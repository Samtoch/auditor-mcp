"""Append-only JSON Lines storage: one JSON object per line."""

import json
import logging
import threading
from pathlib import Path

from auditor_mcp.models.audit import AuditEntry

logger = logging.getLogger(__name__)


class JsonlAuditRepository:
    """Stores audit entries in a single ``.jsonl`` file.

    Writes are serialised with a lock because the MCP SDK runs synchronous
    tool handlers on worker threads, so two calls can arrive at once.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> list[AuditEntry]:
        if not self._path.exists():
            return []
        entries: list[AuditEntry] = []
        with self._lock, self._path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    entries.append(AuditEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, ValueError) as exc:
                    # One bad line (e.g. a partial write) shouldn't hide the rest.
                    logger.warning(
                        "Skipping unreadable line %d in %s: %s", line_no, self._path, exc
                    )
        return entries
