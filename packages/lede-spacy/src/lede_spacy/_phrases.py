"""spaCy-backed phrase extractor.

Uses `doc.noun_chunks` to extract syntactically-grounded noun phrases —
a higher-quality alternative to lede's regex n-gram heuristic. Output
is NOT byte-identical to the regex backend; both are valid implementations
of the same API contract, registered under their respective backend slots.
"""
from __future__ import annotations
import re
from ._ner import _nlp


_WORD_RE = re.compile(r"[a-z]{3,}")


def _clean_chunk(chunk) -> str:
    """Strip leading stopwords/punct from a noun chunk; lowercase; return text."""
    tokens = list(chunk)
    # Strip leading stop/punct
    while tokens and (tokens[0].is_stop or tokens[0].is_punct):
        tokens = tokens[1:]
    # Strip trailing punct (but not trailing stop — rare in noun chunks, and
    # trailing stopwords like "himself" can be semantically meaningful)
    while tokens and tokens[-1].is_punct:
        tokens = tokens[:-1]
    if not tokens:
        return ""
    return " ".join(t.text.lower() for t in tokens)


def spacy_phrases(text: str, keywords: str | None = None) -> tuple[str, ...]:
    """Extract repeated noun phrases via spaCy's noun_chunks.

    Contract matches lede's `phrases(text, keywords)` API:
      - returns phrases that appear >= 2 times, first-appearance order
      - when `keywords` is supplied, also includes single-occurrence phrases
        that contain one of the keyword tokens
    """
    if not text:
        return ()

    doc = _nlp()(text)

    counts: dict[str, int] = {}
    order: list[str] = []
    for chunk in doc.noun_chunks:
        cleaned = _clean_chunk(chunk)
        # Require at least 2 tokens post-clean (match regex backend's "multi-word" intent)
        if not cleaned or len(cleaned.split()) < 2:
            continue
        counts[cleaned] = counts.get(cleaned, 0) + 1
        if counts[cleaned] == 1:
            order.append(cleaned)

    out = [p for p in order if counts[p] >= 2]

    if keywords:
        kw_set = {k for k in _WORD_RE.findall(keywords.lower())}
        for p in order:
            if counts[p] == 1 and any(k in p.split() for k in kw_set):
                out.append(p)

    # Dedupe, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return tuple(deduped)
