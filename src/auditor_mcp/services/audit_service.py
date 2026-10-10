"""Recording and retrieving audited conversation turns."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from auditor_mcp.models import AuditEntry, EntryType, Turn
from auditor_mcp.services.text import limit_words
from auditor_mcp.storage import AuditRepository

logger = logging.getLogger(__name__)

MAX_RECENT_TURNS = 100


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_turn_id() -> str:
    return uuid.uuid4().hex[:12]


class AuditService:
    """Applies the audit rules and hands entries to a repository.

    ``clock`` and ``id_factory`` can be replaced in tests to make output
    deterministic.
    """

    def __init__(
        self,
        repository: AuditRepository,
        word_limit: int,
        *,
        clock: Callable[[], str] = _utc_now,
        id_factory: Callable[[], str] = _new_turn_id,
    ) -> None:
        self._repository = repository
        self._word_limit = word_limit
        self._clock = clock
        self._id_factory = id_factory

    @property
    def word_limit(self) -> int:
        return self._word_limit

    def record_query(
        self,
        text: str,
        is_summary: bool = False,
        original_word_count: int | None = None,
    ) -> AuditEntry:
        """Log the start of a new turn and return the entry, with its new turn_id."""
        entry = self._build_entry(
            EntryType.QUERY, self._id_factory(), text, is_summary, original_word_count
        )
        self._repository.append(entry)
        logger.info("Logged query %s (summary=%s)", entry.turn_id, is_summary)
        return entry

    def record_response(
        self,
        turn_id: str,
        text: str,
        is_summary: bool = False,
        original_word_count: int | None = None,
    ) -> AuditEntry:
        """Log the response for an existing turn."""
        turn_id = turn_id.strip()
        if not turn_id:
            raise ValueError("turn_id is required; use the value returned by log_query.")
        entry = self._build_entry(
            EntryType.RESPONSE, turn_id, text, is_summary, original_word_count
        )
        self._repository.append(entry)
        logger.info("Logged response %s (summary=%s)", turn_id, is_summary)
        return entry

    def recent_turns(self, limit: int = 10) -> list[Turn]:
        """Return the most recent turns, oldest first, each paired with its response."""
        limit = max(1, min(limit, MAX_RECENT_TURNS))
        entries = self._repository.read_all()
        responses = {e.turn_id: e for e in entries if e.type is EntryType.RESPONSE and e.turn_id}
        queries = [e for e in entries if e.type is EntryType.QUERY]
        return [Turn(query=q, response=responses.get(q.turn_id)) for q in queries[-limit:]]

    def _build_entry(
        self,
        entry_type: EntryType,
        turn_id: str,
        text: str,
        is_summary: bool,
        original_word_count: int | None,
    ) -> AuditEntry:
        if not text.strip():
            raise ValueError("text must not be empty.")
        if original_word_count is not None and original_word_count < 0:
            raise ValueError("original_word_count must not be negative.")

        limited = limit_words(text, self._word_limit)
        if original_word_count is None and not is_summary:
            original_word_count = limited.word_count  # verbatim, so the count is exact

        return AuditEntry(
            type=entry_type,
            turn_id=turn_id,
            timestamp=self._clock(),
            text=limited.text,
            is_summary=is_summary,
            truncated_by_server=limited.truncated,
            original_word_count=original_word_count,
        )
