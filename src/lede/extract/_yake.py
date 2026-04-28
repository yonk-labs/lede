"""YAKE-backed phrase extractor. Optional dep: install via `pip install lede[yake]`.

Yet Another Keyword Extractor — statistical, deterministic key-phrase ranker.
Licensed MIT (github.com/LIAAD/yake). Emits ranked multi-word key phrases
scored by position, frequency, casing, and term relatedness. No ML model.

Backend registered as ('yake', 'phrases'). No cross-language parity promise
(Python-only). See docs/lede-spacy-integration.md
for the backend-selector policy — only the 'regex' backend guarantees
Py-Rust byte-identical output.
"""
from __future__ import annotations

from ._backends import register

_YAKE_MODULE = None  # lazy import cache


def _get_yake():
    """Lazy-import the yake package; raise a helpful ImportError when absent."""
    global _YAKE_MODULE
    if _YAKE_MODULE is None:
        try:
            import yake as _yake_pkg
        except ImportError as e:
            raise ImportError(
                "backend='yake' requires the 'yake' optional extra - "
                "install with: pip install lede[yake]"
            ) from e
        _YAKE_MODULE = _yake_pkg
    return _YAKE_MODULE


def _yake_phrases(
    text: str,
    keywords: str | None = None,  # accepted for API symmetry; unused by YAKE
    *,
    n: int = 2,
    top: int = 40,
    dedup_lim: float = 0.9,
    min_words: int = 2,
) -> tuple[str, ...]:
    """YAKE-ranked phrase extractor.

    Returns top-K ranked phrases (lowercased, deduped, multi-word, best-first).

    Defaults tuned against the SC-D phrases corpus (10 files, 115 gold phrases).
    Gold is ~85% bigrams so `n=2, top=40, min_words=2` aligns YAKE's n-gram
    band with the labelers' selection pattern and gives the best F1 trade-off
    observed (P~0.26, R~0.40, F1~0.31). Neither YAKE nor the regex backend
    clears the SC-D gate (R>=0.85, P>=0.80) on this gold; see T13f commit body
    for the full comparison.

    `keywords` is accepted for API symmetry with the other phrase backends but
    is unused — YAKE's own ranking incorporates keyword salience.
    """
    if not text:
        return ()
    yake = _get_yake()
    kw = yake.KeywordExtractor(
        lan="en", n=n, top=top, dedupLim=dedup_lim,
    )
    results = kw.extract_keywords(text)
    # results is list[(phrase, score)] sorted by score ascending (lower = better).
    seen: set[str] = set()
    out: list[str] = []
    for phrase, _score in results:
        p_lower = phrase.lower().strip()
        if not p_lower or p_lower in seen:
            continue
        if len(p_lower.split()) < min_words:
            continue
        seen.add(p_lower)
        out.append(p_lower)
    return tuple(out)


register("yake", "phrases", _yake_phrases)
