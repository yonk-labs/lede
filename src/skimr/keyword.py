"""Keyword-scored extractor: port of extract_sentences() from
extractive_functions.sql.

Bonuses (additive to keyword-match count):
  +0.5 if sentence length > 200 chars
  +0.3 if sentence contains a digit
  +1.0 if sentence contains causal/analytical language
"""
import re

_CAUSAL_RE = re.compile(
    r"(because|reason|due to|caused|result|impact|issue|problem"
    r"|concern|risk|challenge|blocker|gap|lack|missing"
    r"|competitor|pricing|budget|cost|expensive|cheaper|alternative"
    r"|decided|chose|prefer|switched|rejected|declined)",
    re.IGNORECASE,
)
_DIGIT_RE = re.compile(r"\d+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sql_style(text: str) -> list[str]:
    """Match the SQL splitter: replace \\n+ with '. ', then split on [.!?]\\s+."""
    normalized = re.sub(r"\n+", ". ", text)
    parts = _SENTENCE_SPLIT_RE.split(normalized)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def extract_keyword(text: str, keywords: str, num_sentences: int = 10) -> str:
    """Port of extract_sentences(input_text, keywords, num_sentences) from
    extractive_functions.sql.

    Returns top-N sentences newline-joined, ordered by score descending.

    When ``keywords`` is empty or contains only tokens of length ≤ 2,
    returns ``""``. The SQL reference function returned ``LEFT(text, 2000)``
    in this case; we return an empty string instead because a silent
    2000-char chop looked like real output and was a real footgun. Use
    ``summarize()`` if you want a query-less summary.
    """
    if not text:
        return ""

    # Parse keywords: lowercase, split on whitespace, drop tokens <= 2 chars.
    keyword_list = sorted({
        w.lower().strip()
        for w in keywords.split()
        if len(w.strip()) > 2
    })
    if not keyword_list:
        return ""

    sentences = _split_sql_style(text)
    if not sentences:
        return text

    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        lower = s.lower()
        score = sum(1.0 for kw in keyword_list if kw in lower)
        if len(s) > 200:
            score += 0.5
        if _DIGIT_RE.search(s):
            score += 0.3
        if _CAUSAL_RE.search(lower):
            score += 1.0
        scored.append((score, i, s))

    # Sort by (-score, original_position) for deterministic tie-break
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:num_sentences]

    # SQL preserves score-descending order in the output; match it.
    return "\n".join(s for _, _, s in top)
