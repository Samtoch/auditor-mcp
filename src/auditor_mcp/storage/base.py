"""The storage interface the rest of the server depends on."""

from typing import Protocol

from auditor_mcp.models import AuditEntry


class AuditRepository(Protocol):
    """Anything that can store and return audit entries.

    The service layer only depends on this interface, so the JSONL file can
    later be swapped for SQLite, Postgres or a remote API without touching
    the tools.
    """

    def append(self, entry: AuditEntry) -> None:
        """Persist one entry."""
        ...

    def read_all(self) -> list[AuditEntry]:
        """Return every stored entry, oldest first."""
        ...
