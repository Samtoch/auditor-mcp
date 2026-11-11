import pytest

from auditor_mcp.models import EntryType
from auditor_mcp.services import AuditService


def test_verbatim_query_records_exact_word_count(service: AuditService) -> None:
    entry = service.record_query("what is MCP")
    assert entry.type is EntryType.QUERY
    assert entry.turn_id == "turn1"
    assert entry.text == "what is MCP"
    assert entry.original_word_count == 3
    assert not entry.is_summary
    assert not entry.truncated_by_server


def test_summary_keeps_models_estimate(service: AuditService) -> None:
    entry = service.record_query("asks about MCP", is_summary=True, original_word_count=250)
    assert entry.is_summary
    assert entry.original_word_count == 250


def test_over_limit_text_is_truncated_and_flagged(service: AuditService) -> None:
    entry = service.record_query("one two three four five six seven")
    assert entry.text == "one two three four five"
    assert entry.truncated_by_server
    assert entry.original_word_count == 7


def test_response_is_linked_to_its_query(service: AuditService) -> None:
    query = service.record_query("hello")
    service.record_response(query.turn_id, "hi there")

    [turn] = service.recent_turns()
    assert turn.query.text == "hello"
    assert turn.response is not None
    assert turn.response.text == "hi there"


def test_turn_without_response(service: AuditService) -> None:
    service.record_query("hello")
    [turn] = service.recent_turns()
    assert turn.response is None


def test_recent_turns_returns_latest_in_order(service: AuditService) -> None:
    for n in range(5):
        service.record_query(f"query {n}")
    turns = service.recent_turns(limit=2)
    assert [t.query.text for t in turns] == ["query 3", "query 4"]


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_is_rejected(service: AuditService, text: str) -> None:
    with pytest.raises(ValueError, match="text"):
        service.record_query(text)


def test_response_requires_turn_id(service: AuditService) -> None:
    with pytest.raises(ValueError, match="turn_id"):
        service.record_response("  ", "answer")
