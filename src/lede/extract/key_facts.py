"""Key-facts extractor — top-N fact-bearing sentences as complete strings.

Ranked by composite tfidf + stat density, deduped by normalized
(stat_type, value), returned in document order. Composition primitive:
reuses ``stats()`` and ``_composite_score_parts`` — no new regex patterns.

Mirrors rust/src/extract/key_facts.rs. Registered as ('regex','key_facts')
for registry symmetry with the other primitives. No spaCy backend (spaCy
composition path would be a different primitive, not a different backend).
"""
from __future__ import annotations

import re

from ..sentences import split_sentences
from ..tfidf import _composite_score_parts, _TFIDF_WEIGHT, _POSITION_WEIGHT, _LENGTH_WEIGHT
from ._backends import register
from .stats import stats as _stats

# Normalization rule shared with benchmarks/extraction_eval.py::_norm — kept
# in sync by convention (same semantics, local copy to avoid bench dep).
_HYPHEN_RE = re.compile(r"[-_/]+")


def _norm_value(s: str) -> str:
    """Lowercase, hyphen/underscore/slash → space, collapse whitespace.

    Used for dedup key on stat values so "five-day" and "five day" are
    considered the same fact.
    """
    return re.sub(r"\s+", " ", _HYPHEN_RE.sub(" ", s.lower())).strip()


# Stat-density contribution weight in the final score. Kept small so the
# composite tfidf signal still dominates.
_STAT_DENSITY_WEIGHT = 0.15


def key_facts(
    text: str,
    *,
    max_facts: int = 10,
    convert_word_names: bool = False,
) -> tuple[str, ...]:
    """Return top-N sentences containing numeric/named facts.

    Candidates are any sentence that produces at least one ``Stat`` from
    ``stats(text, convert_word_names=convert_word_names)``. Each candidate
    is scored as:

        0.60*tfidf + 0.25*position + 0.15*length
        + 0.15 * (num_stats_in_sentence / sentence_len_in_tokens)

    Candidates are deduped by the normalized ``(stat_type, value)`` key:
    if two sentences share any such key, only the higher-scored one is
    kept. Ties broken by earlier document position (deterministic).

    The top ``max_facts`` survivors are returned in **document order**
    (not score order) — readers want reading flow.

    Args:
        text: input document text.
        max_facts: cap on number of returned sentences. Default 10.
        convert_word_names: forwarded to ``stats()``; requires the
            'wordforms' extra when True.

    Returns:
        Tuple of complete sentence strings (not ``Stat`` tuples). Empty
        tuple when no sentence contains a recognized fact.
    """
    if not text:
        return ()

    all_stats = _stats(text, convert_word_names=convert_word_names)
    if not all_stats:
        return ()

    sentences = split_sentences(text)
    if not sentences:
        return ()

    # Group stats by their context_sentence. We walk sentences in order and
    # match on string equality (context_sentence is a direct slice of the
    # input, same as the one split_sentences returns).
    stats_by_sentence: dict[int, list] = {}
    # Build a sentence-string → index lookup for O(1) grouping. When the same
    # sentence appears twice in a document the first occurrence wins — this
    # is deterministic and matches how stats() emits context_sentence.
    sent_to_idx: dict[str, int] = {}
    for i, s in enumerate(sentences):
        sent_to_idx.setdefault(s, i)
    for stat in all_stats:
        idx = sent_to_idx.get(stat.context_sentence)
        if idx is None:
            continue
        stats_by_sentence.setdefault(idx, []).append(stat)

    if not stats_by_sentence:
        return ()

    parts = _composite_score_parts(sentences)

    candidates: list[tuple[float, int, list]] = []
    for idx, stat_list in stats_by_sentence.items():
        t, p, l_ = parts[idx]
        composite = _TFIDF_WEIGHT * t + _POSITION_WEIGHT * p + _LENGTH_WEIGHT * l_
        # Sentence length in whitespace-separated tokens; mirrors how
        # length_score counts words. Guarded against zero for safety.
        tok_count = max(1, len(sentences[idx].split()))
        density = len(stat_list) / tok_count
        score = composite + _STAT_DENSITY_WEIGHT * density
        candidates.append((score, idx, stat_list))

    # Dedup by (stat_type, normalized value). Walk candidates in
    # score-descending order; for each, if any of its (stat_type, norm_value)
    # keys collide with an already-kept candidate, drop the later one.
    # Ties on score broken by earlier document position.
    candidates.sort(key=lambda c: (-c[0], c[1]))
    kept_keys: set[tuple[str, str]] = set()
    kept: list[tuple[float, int]] = []
    for score, idx, stat_list in candidates:
        keys = {(s.stat_type, _norm_value(s.value)) for s in stat_list}
        if keys & kept_keys:
            continue
        kept_keys.update(keys)
        kept.append((score, idx))
        if len(kept) >= max_facts:
            break

    # Return in document order.
    kept.sort(key=lambda c: c[1])
    return tuple(sentences[i] for _, i in kept)


register("regex", "key_facts", key_facts)
