from auditor_mcp.services import limit_words


def test_short_text_is_kept() -> None:
    result = limit_words("one two three", 5)
    assert result.text == "one two three"
    assert result.word_count == 3
    assert not result.truncated


def test_long_text_is_cut_to_limit() -> None:
    result = limit_words("a b c d e f g", 5)
    assert result.text == "a b c d e"
    assert result.word_count == 7
    assert result.truncated


def test_whitespace_is_collapsed() -> None:
    assert limit_words("line one\n\nline   two", 10).text == "line one line two"
