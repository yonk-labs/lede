"""lede_spacy.expand_hints — expand hint terms for use with lede's hint biasing.

Three kinds:
- "lemma" (default): use spaCy's lemmatizer (T14)
- "synonyms": WordNet via nltk (T15 — gated behind [synonyms] extra)
- "similar": spaCy word vectors (T16 — requires en_core_web_md or _lg)

Composes with lede core: caller expands hints, then passes the result
to lede.summarize / brief / extract.* via `hints=`.
"""
from __future__ import annotations

from ._ner import _nlp


_VALID_KINDS = ("lemma", "synonyms", "similar")


def _lemmatize_phrase(phrase: str) -> str:
    """Tokenize phrase with spaCy, lemmatize each token, rejoin with single spaces."""
    doc = _nlp()(phrase)
    return " ".join(tok.lemma_ for tok in doc).strip()


def _expand_lemma(term: str) -> list[str]:
    """Return [original, lemmatized] deduped (original first; lemmatized only if different)."""
    lemmatized = _lemmatize_phrase(term)
    if lemmatized and lemmatized.lower() != term.lower():
        return [term, lemmatized]
    return [term]


def _expand_synonyms(term: str, *, top_k: int) -> list[str]:
    """Expand via WordNet synonyms. Requires lede-spacy[synonyms]."""
    from ._synonyms import expand_synonyms
    return expand_synonyms(term, top_k=top_k)


def _expand_similar(term: str, *, top_k: int) -> list[str]:
    """Placeholder — T16 will implement via spaCy vectors."""
    raise NotImplementedError("similar expansion lands in T16")


def expand_hints(
    hints: list[str] | dict[str, float],
    *,
    kinds: tuple[str, ...] = ("lemma",),
    top_k: int = 5,
    expand_weight: float = 0.5,
) -> list[str] | dict[str, float]:
    """Expand hint terms for lede's hint biasing.

    Args:
        hints: list[str] or dict[str, float]. Hints to expand.
        kinds: tuple of expansion kinds. Supported: "lemma", "synonyms", "similar".
        top_k: cap on expansions per single-token hint (synonyms/similar).
        expand_weight: dict-mode multiplier applied to expansion-term weights.

    Returns:
        list[str] when input is list, dict[str, float] when input is dict.

    Raises:
        ValueError: on unknown kinds.
        ImportError: when "synonyms" requested without lede-spacy[synonyms] installed.
        NotImplementedError: when "similar" requested (pending T16).

    Example::

        from lede import summarize
        from lede_spacy import expand_hints

        hints = expand_hints(["counties"], kinds=("lemma",))
        # hints == ["counties", "county"]
        result = summarize(text, hints=hints).summary
    """
    is_dict = isinstance(hints, dict)
    if not hints:
        return {} if is_dict else []

    for k in kinds:
        if k not in _VALID_KINDS:
            raise ValueError(f"unknown kind: {k!r}; expected one of {_VALID_KINDS}")

    items: list[tuple[str, float]] = (
        list(hints.items()) if is_dict else [(h, 1.0) for h in hints]
    )

    # term -> max(weight) seen
    expanded: dict[str, float] = {}
    for term, weight in items:
        # Preserve original at its full weight.
        expanded[term] = max(expanded.get(term, 0.0), float(weight))

        for kind in kinds:
            if kind == "lemma":
                additions = _expand_lemma(term)
            elif kind == "synonyms":
                additions = _expand_synonyms(term, top_k=top_k)
            elif kind == "similar":
                additions = _expand_similar(term, top_k=top_k)
            else:
                continue
            for add in additions:
                if add == term:
                    continue
                scaled = float(weight) * expand_weight
                expanded[add] = max(expanded.get(add, 0.0), scaled)

    if is_dict:
        return expanded

    # Preserve insertion order from the expanded dict, casefold-dedup.
    seen: set[str] = set()
    out: list[str] = []
    for k in expanded:
        low = k.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(k)
    return out
