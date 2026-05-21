"""Internal: hint preprocessing, matching, scoring, two-pool selection.

All names are package-private (underscore module). Public surface is the
hint kwargs on lede.summarize / brief / extract.* primitives.

Must remain byte-identical to rust/src/hints.rs.
"""
from __future__ import annotations

import re
from typing import Iterable

_WHITESPACE_RE = re.compile(r"\s+")

# Cache compiled per-hint regexes. Bounded — most processes use a small
# stable set of hints. If callers churn through thousands of distinct
# hint strings, this cache grows; that's their bandwidth call.
_REGEX_CACHE: dict[str, re.Pattern] = {}

_HINT_BASE_WEIGHT = 0.5
_HINT_MATCH_CAP = 3


def preprocess_hints(
    hints: list[str] | dict[str, float] | None,
) -> list[tuple[str, float]]:
    """Return list of (lowercased_hint, weight) tuples.

    - Strips, collapses internal whitespace, lowercases.
    - Drops empty/whitespace-only entries.
    - List input → weight 1.0 per hint.
    - Dict input → uses values as weights.
    - None or empty → empty list.
    """
    if not hints:
        return []
    out: list[tuple[str, float]] = []
    if isinstance(hints, dict):
        items: Iterable[tuple[str, float]] = hints.items()
    else:
        items = ((h, 1.0) for h in hints)
    for raw, weight in items:
        if not isinstance(raw, str):
            continue
        stripped = raw.strip()
        if not stripped:
            continue
        collapsed = _WHITESPACE_RE.sub(" ", stripped)
        out.append((collapsed.lower(), float(weight)))
    return out


def _compile_hint(hint: str) -> re.Pattern:
    """Compile and cache the word-boundary regex for a preprocessed hint."""
    cached = _REGEX_CACHE.get(hint)
    if cached is not None:
        return cached
    pattern = re.compile(r"\b" + re.escape(hint) + r"\b")
    _REGEX_CACHE[hint] = pattern
    return pattern


def match_count(hint: str, sentence: str) -> int:
    """Non-overlapping match count for one preprocessed hint vs. sentence.

    Caller is responsible for preprocessing the hint via `preprocess_hints`.
    The sentence is lowercased here; preprocessing the hint there.
    """
    if not hint:
        return 0
    return len(_compile_hint(hint).findall(sentence.lower()))
