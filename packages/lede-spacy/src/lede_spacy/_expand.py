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
    """Expand via spaCy word-vector similarity. Requires en_core_web_md or _lg.

    Loads a vector-capable model (``$LEDE_SPACY_VECTOR_MODEL`` or en_core_web_md)
    rather than the default sm, which has no vectors.
    """
    import os
    from ._similar import expand_similar
    model = os.environ.get("LEDE_SPACY_VECTOR_MODEL", "en_core_web_md")
    return expand_similar(_nlp(model), term, top_k=top_k)


def expand_hints(
    hints: list[str] | dict[str, float],
    *,
    kinds: tuple[str, ...] = ("lemma",),
    top_k: int = 5,
    expand_weight: float = 0.5,
) -> list[str] | dict[str, float]:
    """Expand hint terms for lede's hint biasing (v0.4).

    Augments the caller-supplied hints with related forms before passing
    them to ``lede.summarize``, ``lede.brief``, or any ``lede.extract.*``
    primitive. The original terms are always preserved at their full weight;
    expansion terms are added alongside them.

    Args:
        hints: list[str] or dict[str, float]. The original hints to expand.
            Each string is treated independently; multi-token phrases are
            passed whole to the lemmatizer but are skipped by the
            synonyms/similar expanders (which are single-token-only).
        kinds: tuple of expansion strategies to apply. Any non-empty subset
            of ``("lemma", "synonyms", "similar")``. Default ``("lemma",)``.

            - ``"lemma"`` — uses the loaded spaCy model's lemmatizer.
              Requires any spaCy model (``en_core_web_sm`` or larger).
              Multi-token phrases are lemmatized token-by-token and rejoined.
              Example: ``"counties"`` → adds ``"county"``.

            - ``"synonyms"`` — expands via WordNet synonyms (nltk).
              Requires ``pip install lede-spacy[synonyms]`` (pulls ``nltk``
              + the ``wordnet`` corpus). Single-token terms only; phrases
              are skipped. Example: ``"county"`` → adds ``"region"``,
              ``"district"``, etc. (up to ``top_k``).

            - ``"similar"`` — expands via spaCy word-vector cosine
              similarity. Requires a vector-capable model such as
              ``en_core_web_md`` or ``en_core_web_lg`` (the default
              ``en_core_web_sm`` has no vectors). Single-token terms only.
              Returns the ``top_k`` most similar vocab entries by cosine.

        top_k: maximum number of expansion terms added per single-token
            hint for the ``"synonyms"`` and ``"similar"`` strategies.
            Has no effect on ``"lemma"`` (which adds at most one form).
            Default 5.
        expand_weight: when ``hints`` is a dict, expansion terms are
            assigned weight ``original_weight * expand_weight``. Original
            terms keep their supplied weight unchanged. Default 0.5, meaning
            expansion forms are half as strongly weighted as the originals.
            Has no effect when ``hints`` is a list (all weights are 1.0 and
            expansion terms are just appended without weights).

    Returns:
        - ``list[str]`` when ``hints`` is a list — original terms plus
          expansion terms, casefold-deduped, original insertion order
          preserved.
        - ``dict[str, float]`` when ``hints`` is a dict — original terms
          at their original weights plus expansion terms at
          ``weight * expand_weight``. If an expansion term was already
          present as an original, it keeps the higher of the two weights.

    Raises:
        ValueError: on unknown entry in ``kinds``.
        ImportError: when ``"synonyms"`` is requested but
            ``lede-spacy[synonyms]`` is not installed (``nltk`` missing or
            the ``wordnet`` corpus not downloaded).
        RuntimeError: when ``"similar"`` is requested but the loaded spaCy
            model has no word vectors (e.g. ``en_core_web_sm``).

    Example — compose with ``lede.summarize``::

        from lede import summarize
        from lede_spacy import expand_hints

        # Lemma expansion: "counties" → ["counties", "county"]
        hints = expand_hints(["counties"], kinds=("lemma",))
        result = summarize(text, hints=hints, hint_focus=0.7).summary

    Example — dict mode with weighted synonyms::

        from lede_spacy import expand_hints

        expanded = expand_hints(
            {"county": 1.0, "sheriff": 1.0},
            kinds=("lemma", "synonyms"),
            top_k=3,
            expand_weight=0.5,
        )
        # expanded == {"county": 1.0, "region": 0.5, "district": 0.5,
        #              "sheriff": 1.0, ...}
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
