"""Text helpers for enforcing the word limit."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LimitedText:
    text: str
    word_count: int
    truncated: bool


def limit_words(text: str, limit: int) -> LimitedText:
    """Keep at most ``limit`` words of ``text``.

    Words are whitespace-separated, so line breaks are collapsed to single
    spaces in the result.
    """
    words = text.split()
    return LimitedText(
        text=" ".join(words[:limit]),
        word_count=len(words),
        truncated=len(words) > limit,
    )
