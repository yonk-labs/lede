"""TF-IDF + position + length extractive summarization pipeline.

Per SUMMARIZATION.md:
  score = 0.60 * tfidf + 0.25 * position + 0.15 * length

All scores normalized to [0, 1] per dimension. The composite is a weighted
sum, also in [0, 1].
"""
import math
import re
from collections import Counter

from skimr.sentences import split_sentences

_TFIDF_WEIGHT = 0.60
_POSITION_WEIGHT = 0.25
_LENGTH_WEIGHT = 0.15

# Basic stopword list — deliberately small and stable across languages.
# Shared with the cross-language fixture corpus; do not add locale-specific terms.
_STOPWORDS = frozenset({
    "the", "and", "that", "this", "with", "for", "are", "was", "were",
    "been", "have", "has", "had", "not", "but", "what", "all", "when",
    "who", "will", "can", "from", "they", "each", "which", "their",
    "there", "about", "would", "make", "more", "some", "into",
    "other", "than", "its", "also", "after", "use", "how", "our",
    "any", "these", "most", "may", "should", "could", "does", "did",
    "just", "because", "over", "such", "through", "very", "your",
    "a", "an", "is", "it", "in", "on", "of", "to", "be", "as", "at", "by",
})

_TOKEN_RE = re.compile(r"\b[a-z]{3,}\b")


def _tokenize(sentence: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(sentence.lower()) if t not in _STOPWORDS]


def _normalize(scores: list[float]) -> list[float]:
    hi = max(scores, default=0.0)
    if hi <= 0.0:
        return [0.0] * len(scores)
    return [s / hi for s in scores]


def tfidf_score(sentences: list[str]) -> list[float]:
    """TF-IDF score per sentence, normalized to [0, 1]."""
    tokenized = [_tokenize(s) for s in sentences]
    n = len(sentences)

    # Document frequency: how many sentences contain each term
    df: Counter[str] = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1

    # IDF — smoothed to avoid log(1) = 0 for universal terms
    idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    raw: list[float] = []
    for tokens in tokenized:
        if not tokens:
            raw.append(0.0)
            continue
        tf = Counter(tokens)
        # Sum of tf-idf, divided by sentence length — average term importance
        score = sum(tf[term] * idf.get(term, 0.0) for term in tf) / len(tokens)
        raw.append(score)

    return _normalize(raw)


def position_score(n: int) -> list[float]:
    """Position score: first and last sentences score 1.0, middle scores lower.

    Uses a U-shape: score(i) = max(1 - i/n, i/n). For i=0 or i=n-1, this is 1.0.
    """
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    scores: list[float] = []
    for i in range(n):
        # Distance from the nearer endpoint, normalized
        d = min(i, n - 1 - i) / max(n - 1, 1)
        # d=0 at endpoints, d=0.5 at middle. Score = 1 - 2d gives 1 at ends, 0 at middle.
        scores.append(max(0.0, 1.0 - 2.0 * d))
    # Endpoints are already 1.0; normalize is a no-op but keeps shape consistent
    return _normalize(scores)


def length_score(sentences: list[str]) -> list[float]:
    """Length score: peaks in 10-30 word range per SUMMARIZATION.md."""
    raw: list[float] = []
    for s in sentences:
        words = len(s.split())
        if words == 0:
            raw.append(0.0)
        elif 10 <= words <= 30:
            raw.append(1.0)
        elif words < 10:
            raw.append(words / 10.0)
        else:  # words > 30
            # Linear decay to 0 by word count 80
            raw.append(max(0.0, 1.0 - (words - 30) / 50.0))
    return _normalize(raw)


def composite_score(sentences: list[str]) -> list[float]:
    """Composite score: 0.60 * tfidf + 0.25 * position + 0.15 * length."""
    if not sentences:
        return []
    t = tfidf_score(sentences)
    p = position_score(len(sentences))
    l = length_score(sentences)
    return [
        _TFIDF_WEIGHT * t[i] + _POSITION_WEIGHT * p[i] + _LENGTH_WEIGHT * l[i]
        for i in range(len(sentences))
    ]


# --- Top-level summarize pipeline ---

_MIN_SENTENCES = 3
_MIN_BUDGET_FOR_SENTENCES = 50  # chars; below this, truncate


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    # Reserve 3 chars for the ellipsis
    body_budget = max(0, max_length - 3)
    return text[:body_budget] + "..."


def summarize(text: str, max_length: int = 500) -> str:
    """Extractive summary of ``text`` capped at ``max_length`` characters.

    Per SUMMARIZATION.md:
      1. If input fits the budget, return unchanged.
      2. If the budget is too small for sentences, truncate.
      3. Split into sentences; if fewer than 3, truncate.
      4. Score sentences (TF-IDF + position + length, 60/25/15).
      5. Greedily add highest-scoring sentences until the char budget is spent.
      6. Reorder selected sentences by original position.
      7. Fallback to truncation if selection is empty.
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return _truncate(text, max_length)

    sentences = split_sentences(text)
    if len(sentences) < _MIN_SENTENCES:
        return _truncate(text, max_length)

    scores = composite_score(sentences)
    # Indices sorted by score descending, then by original position ascending
    # (stable tie-break — deterministic).
    indices_by_score = sorted(
        range(len(sentences)),
        key=lambda i: (-scores[i], i),
    )

    selected: list[int] = []
    used = 0
    separator = " "
    for idx in indices_by_score:
        sentence = sentences[idx]
        needed = len(sentence) + (len(separator) if selected else 0)
        if used + needed <= max_length:
            selected.append(idx)
            used += needed

    if not selected:
        return _truncate(text, max_length)

    selected.sort()
    return separator.join(sentences[i] for i in selected)
