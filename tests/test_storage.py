import json

from auditor_mcp.models import AuditEntry, EntryType
from auditor_mcp.storage import JsonlAuditRepository


def test_round_trip(repository: JsonlAuditRepository) -> None:
    entry = AuditEntry(EntryType.QUERY, "t1", "2026-10-10T00:00:00+00:00", "hello")
    repository.append(entry)
    assert repository.read_all() == [entry]


def test_missing_file_reads_as_empty(repository: JsonlAuditRepository) -> None:
    assert repository.read_all() == []


def test_bad_lines_are_skipped(repository: JsonlAuditRepository) -> None:
    good = AuditEntry(EntryType.QUERY, "t1", "ts", "hello")
    repository.append(good)
    with repository.path.open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    assert repository.read_all() == [good]


def test_reads_entries_from_earlier_versions(repository: JsonlAuditRepository) -> None:
    legacy = [
        {"timestamp": "ts1", "query": "very old entry"},
        {"type": "query", "turn_id": "abc", "timestamp": "ts2", "query": "v2 query"},
        {
            "type": "response",
            "turn_id": "abc",
            "timestamp": "ts3",
            "excerpt": "v2 answer",
            "words_received": 120,
            "truncated": True,
        },
    ]
    repository.path.write_text("\n".join(json.dumps(e) for e in legacy) + "\n", encoding="utf-8")

    old, query, response = repository.read_all()
    assert old.type is EntryType.QUERY and old.text == "very old entry" and old.turn_id == ""
    assert query.text == "v2 query"
    assert response.text == "v2 answer"
    assert response.truncated_by_server
    assert response.original_word_count == 120
