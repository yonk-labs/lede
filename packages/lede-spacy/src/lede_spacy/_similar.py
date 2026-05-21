"""spaCy word-vector expansion for lede_spacy.expand_hints.

Requires a spaCy model with word vectors loaded (`en_core_web_md` or
`en_core_web_lg`). The default `en_core_web_sm` has no vectors.
"""
from __future__ import annotations


def _model_has_vectors(nlp) -> bool:
    """True when the loaded nlp pipeline has non-zero word vectors."""
    return nlp.vocab.vectors_length > 0


def expand_similar(nlp, term: str, *, top_k: int) -> list[str]:
    """Return up to top_k highest-cosine-similarity lexemes for a single-token term.

    Multi-token terms return [] (caller treats this as passthrough).
    Determinism: sorted by (-similarity, token_text). Stop words, OOV
    tokens, and the term itself are excluded.

    Raises:
        RuntimeError: when the loaded spaCy model has no word vectors.
    """
    if " " in term.strip():
        return []
    if not _model_has_vectors(nlp):
        model_name = nlp.meta.get("name", "<unknown>")
        raise RuntimeError(
            "expand_hints(kinds=('similar',)) requires en_core_web_md or "
            f"en_core_web_lg; loaded model {model_name!r} has no vectors. "
            "Install with: python -m spacy download en_core_web_md"
        )

    token = nlp(term)[0]
    if not token.has_vector:
        return []

    # Walk the vocab, score by cosine similarity to the input token.
    # Filter: must be lowercase, alphabetic, not a stop word, have a vector,
    # and not be the same lemma as the input.
    candidates: list[tuple[float, str]] = []
    term_low = term.lower()
    for lex in nlp.vocab:
        if not lex.has_vector or lex.is_stop or not lex.is_alpha:
            continue
        if not lex.is_lower:
            continue
        if lex.text.lower() == term_low:
            continue
        sim = token.similarity(lex)
        if sim <= 0.0:
            continue
        candidates.append((-sim, lex.text))

    candidates.sort()  # ascending by (-sim, text) → highest similarity first, ties by text
    out: list[str] = []
    seen: set[str] = set()
    for _neg, name in candidates:
        low = name.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(name)
        if len(out) >= top_k:
            break
    return out
