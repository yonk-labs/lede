"""Sentence splitter.

Splits on sentence-terminal punctuation (.!?) followed by whitespace and an
uppercase letter, plus paragraph breaks. Protects known abbreviations and
decimal numbers from being treated as sentence boundaries.
"""
import re

# Abbreviations where a trailing period should NOT end a sentence.
# Lowercase compared, case-insensitively matched.
_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "st", "sr", "jr",
    "inc", "ltd", "co", "corp",
    "vs", "etc", "eg", "ie", "cf",
    "u.s", "u.k", "u.n", "e.u",
    "fig", "no", "vol",
})

_SENTINEL = "\x00"  # ASCII NUL — won't appear in real text


def _mask(text: str) -> str:
    # Protect decimals: digit.digit → digit<SENTINEL>digit
    text = re.sub(r"(\d)\.(\d)", lambda m: f"{m.group(1)}{_SENTINEL}{m.group(2)}", text)

    # Protect known abbreviations. Match word boundary + abbrev + dot.
    def _abbrev_sub(match: re.Match) -> str:
        word = match.group(1)
        if word.lower() in _ABBREVIATIONS:
            return f"{word}{_SENTINEL}"
        return match.group(0)

    # Match (word).(lookahead: whitespace or end). This covers "Dr." and "U.S."
    text = re.sub(r"\b([A-Za-z]+(?:\.[A-Za-z]+)*)\.", _abbrev_sub, text)
    return text


def _unmask(text: str) -> str:
    return text.replace(_SENTINEL, ".")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Returns a list; empty input returns []."""
    if not text:
        return []

    masked = _mask(text)

    # Split on paragraph breaks (2+ newlines) OR terminal punct + whitespace + uppercase start.
    # Use a single combined splitter. We keep the terminator by splitting AFTER it.
    parts: list[str] = []
    pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n\s*\n")
    for piece in pattern.split(masked):
        piece = piece.strip()
        if piece:
            parts.append(_unmask(piece))

    return parts
