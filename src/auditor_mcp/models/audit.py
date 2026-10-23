"""Domain models for the audit log."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class EntryType(StrEnum):
    QUERY = "query"
    RESPONSE = "response"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One line of the audit log: a user query or a response to it.

    Attributes:
        type: Whether this records a query or a response.
        turn_id: Links a response to the query that started its turn.
        timestamp: UTC time the entry was recorded, ISO 8601.
        text: The stored text, never longer than the configured word limit.
        is_summary: True if ``text`` is a summary written by the model,
            False if it is the original wording.
        truncated_by_server: True if the server had to cut ``text`` down
            to the word limit.
        original_word_count: Length of the original text. Exact for verbatim
            entries; the model's estimate for summaries.
    """

    type: EntryType
    turn_id: str
    timestamp: str
    text: str
    is_summary: bool = False
    truncated_by_server: bool = False
    original_word_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        """Parse a stored entry, including entries written by earlier versions.

        Earlier versions stored the text under ``query`` or ``excerpt`` and
        did not always record ``type`` or ``turn_id``.
        """
        text = data.get("text") or data.get("query") or data.get("excerpt") or ""
        return cls(
            type=EntryType(data.get("type", EntryType.QUERY)),
            turn_id=data.get("turn_id") or "",
            timestamp=data.get("timestamp", ""),
            text=text,
            is_summary=bool(data.get("is_summary", False)),
            truncated_by_server=bool(data.get("truncated_by_server", data.get("truncated", False))),
            original_word_count=data.get("original_word_count", data.get("words_received")),
        )


@dataclass(frozen=True, slots=True)
class Turn:
    """A query paired with its response, if one was logged."""

    query: AuditEntry
    response: AuditEntry | None = None
