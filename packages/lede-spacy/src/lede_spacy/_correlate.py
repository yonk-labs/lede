"""spaCy-backed correlate_facts — dep-parse + NER entity-number pairings.

Pairs repeated entities with numeric facts using spaCy's dependency parser
and NER rather than the regex backend's stats() + phrase-overlap heuristic.
Registered as ('spacy', 'correlate_facts').

Not byte-identical to the regex backend; both are valid implementations of
the same API contract. Output is deterministic for a fixed spaCy model
version (en_core_web_sm-3.8.0 pinned in lede-spacy).
"""
from __future__ import annotations
from collections import Counter

from lede._types import PhraseFact
from ._ner import _nlp


# Entity labels that count as "entities" for correlation purposes — the
# same proper-noun-ish set as _ner plus a few context-worthy additions.
_ENTITY_LABELS = frozenset({
    "PERSON", "ORG", "GPE", "LOC", "PRODUCT",
    "FAC", "WORK_OF_ART", "EVENT", "NORP",
})

# Polarity cue lemmas. Verb lemmas in spaCy are lowercase infinitives.
_GROWTH_LEMMAS = frozenset({
    "grow", "increase", "rise", "gain", "add", "climb", "surge",
    "expand", "jump", "soar",
})
_DECLINE_LEMMAS = frozenset({
    "fall", "decline", "decrease", "drop", "lose", "shrink",
    "contract", "plunge", "slip", "downgrade",
})


def _clean_chunk_text(chunk) -> str:
    """Lowercase noun-chunk text, stripping leading det/stopwords + punctuation.

    Mirrors the cleaning in `_phrases.py` so entity strings look the same
    whether they come from NER or from noun_chunks.
    """
    tokens = list(chunk)
    while tokens and (tokens[0].is_stop or tokens[0].is_punct or tokens[0].pos_ == "DET"):
        tokens = tokens[1:]
    while tokens and tokens[-1].is_punct:
        tokens = tokens[:-1]
    if not tokens:
        return ""
    return " ".join(t.text.lower() for t in tokens)


def _collect_entity_spans(doc) -> list:
    """Return spans that name a candidate entity.

    Combines NER-detected entities (wanted labels) with multi-token noun
    chunks. Duplicates (same (start, end)) are dropped; NER spans win when
    they overlap with a noun chunk that has the same boundaries.

    Entity *mention frequency* is computed by surface text (after
    `_span_text` normalization) — callers use that to filter out
    one-off mentions before emitting pairings.
    """
    spans = []
    seen_bounds: set[tuple[int, int]] = set()

    # NER spans first — preferred source for named entities.
    for ent in doc.ents:
        if ent.label_ in _ENTITY_LABELS:
            key = (ent.start, ent.end)
            if key not in seen_bounds:
                seen_bounds.add(key)
                spans.append(ent)

    # Multi-token noun chunks — catch things like "risk register" that NER
    # misses. Single-token chunks are too noisy (every pronoun, every
    # common noun) — skip them.
    for chunk in doc.noun_chunks:
        if len(chunk) < 2:
            continue
        key = (chunk.start, chunk.end)
        if key in seen_bounds:
            continue
        seen_bounds.add(key)
        spans.append(chunk)

    return spans


def _span_text(span) -> str:
    """Return the cleaned, lowercased text for either an NER ent or a noun chunk."""
    # Noun chunks get the leading-det/stopword scrub; NER spans pass through
    # as-is (just lowercased) so "Cascade Processing LLC" stays intact.
    if getattr(span, "label_", "") in _ENTITY_LABELS:
        return span.text.strip().lower()
    return _clean_chunk_text(span)


def _is_number_token(tok) -> bool:
    """A token that represents a numeric quantity we care about."""
    if tok.is_stop or tok.is_punct:
        return False
    if tok.pos_ == "NUM":
        return True
    # `like_num` catches spelled-out numbers ("three", "eight") that the
    # tagger may not always tag NUM.
    if tok.like_num and tok.pos_ not in ("DET", "PRON"):
        return True
    return False


def _number_phrase(tok) -> str:
    """Return a short phrase representing the number: the number + its head noun
    when head is a noun (e.g. "eight days", "seven days", "14 percent")."""
    head = tok.head
    if head is not None and head.pos_ == "NOUN" and head.i != tok.i:
        # Keep only the numeric modifier + head noun, in document order.
        lo, hi = min(tok.i, head.i), max(tok.i, head.i)
        return " ".join(t.text for t in tok.doc[lo:hi + 1]).strip()
    return tok.text


def _infer_polarities(sent) -> tuple[str, ...]:
    """Return all polarity cues in the sentence.

    A sentence can carry multiple polarity signals — e.g. "three items
    added, two downgraded" has both growth (add) and decline (downgrade).
    Returns ('absolute',) if no cue fires.
    """
    polarities: list[str] = []
    seen: set[str] = set()
    for tok in sent:
        if tok.pos_ == "VERB":
            lemma = tok.lemma_.lower()
            if lemma in _GROWTH_LEMMAS and "growth" not in seen:
                polarities.append("growth")
                seen.add("growth")
            elif lemma in _DECLINE_LEMMAS and "decline" not in seen:
                polarities.append("decline")
                seen.add("decline")
    if not polarities:
        return ("absolute",)
    return tuple(polarities)


def _canonical_text(raw: str) -> str:
    """Normalize an entity surface form into a comparable canonical.

    Strips leading articles, trailing possessives ('s / '), and basic
    punctuation noise. Keeps meaningful multi-word structure intact.
    """
    text = raw.strip().lower()
    # Remove leading articles
    for article in ("the ", "a ", "an "):
        if text.startswith(article):
            text = text[len(article):]
            break
    # Strip trailing possessive indicators
    if text.endswith("'s"):
        text = text[:-2].strip()
    elif text.endswith(" 's"):
        text = text[:-3].strip()
    elif text.endswith("'"):
        text = text[:-1].strip()
    return text


def _extract_pairings(doc) -> list[PhraseFact]:
    entities = _collect_entity_spans(doc)
    if not entities:
        return []

    # Map each span to its normalized canonical text, and count sentence
    # frequency per canonical. Same entity appearing twice in one
    # sentence only counts as one mention.
    span_canon: dict[int, str] = {}
    canonical_sentences: dict[str, set[int]] = {}
    for e in entities:
        raw = _span_text(e)
        canon = _canonical_text(raw)
        if not canon:
            continue
        # Discard canonicals that reduce to a single short/stopword-like
        # token — they're too ambiguous for correlation signal.
        if len(canon) < 3:
            continue
        span_canon[e.start] = canon
        for sent in doc.sents:
            if e.start >= sent.start and e.end <= sent.end:
                canonical_sentences.setdefault(canon, set()).add(sent.start)
                break

    # Precision filter: entity must appear in >= 2 distinct sentences.
    # Exception: compact 2-token noun-chunks that share a sentence with a
    # numeric stat often encode the salient correlation even on a single
    # mention ("risk register has grown", "canary period — seven days").
    # We admit these as single-sentence candidates.
    repeated_canonicals = {
        c for c, sents in canonical_sentences.items() if len(sents) >= 2
    }
    singleton_admit: set[str] = set()
    for c, sents in canonical_sentences.items():
        if c in repeated_canonicals:
            continue
        toks = c.split()
        if 2 <= len(toks) <= 3 and all(len(t) >= 3 for t in toks):
            singleton_admit.add(c)
    allowed_canonicals = repeated_canonicals | singleton_admit
    if not allowed_canonicals:
        return []

    out: list[PhraseFact] = []
    for sent in doc.sents:
        sent_entities: list[tuple[str, int, int]] = []
        for e in entities:
            if not (e.start >= sent.start and e.end <= sent.end):
                continue
            canon = span_canon.get(e.start)
            if canon is None:
                continue
            if canon in allowed_canonicals:
                sent_entities.append((canon, e.start, e.end))
        if not sent_entities:
            continue
        nums = [t for t in sent if _is_number_token(t)]
        if not nums:
            continue

        polarities = _infer_polarities(sent)
        sent_text = sent.text.strip()

        seen_keys: set[tuple[str, str, str]] = set()
        for num_tok in nums:
            # Do not cross-product every entity with every number in the
            # sentence. That explodes on structured docs where a Markdown
            # heading/header block is parsed as one spaCy sentence. Pair each
            # number with the nearest admitted entity span in the sentence.
            canon, _start, _end = min(
                sent_entities,
                key=lambda item: (
                    0
                    if item[1] <= num_tok.i < item[2]
                    else min(abs(num_tok.i - item[1]), abs(num_tok.i - (item[2] - 1))),
                    item[1],
                    item[0],
                ),
            )
            num_phrase = _number_phrase(num_tok)
            for polarity in polarities:
                key = (canon, num_phrase, polarity)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                out.append(PhraseFact(
                    entity=canon,
                    number=num_phrase,
                    polarity=polarity,
                    sentence=sent_text,
                ))
    return out


def spacy_correlate_facts(text: str) -> tuple[PhraseFact, ...]:
    """Pair repeated entities with numeric facts, using spaCy dep-parse + NER.

    Pipeline:
      1. Parse text with spaCy.
      2. Collect entity spans: NER labels (PERSON/ORG/GPE/...) + multi-token
         noun chunks.
      3. Canonicalize surface text (strip leading articles, trailing
         possessives) so "the Agency" and "Agency" land in the same bucket.
      4. Admit an entity for pairing if it appears in >= 2 distinct
         sentences, OR if it is a compact 2-3 token noun-chunk that
         co-occurs with a numeric fact (single-sentence salience).
      5. For each sentence containing both an admitted entity and a
         number token (POS=NUM or like_num), emit one PhraseFact per
         (entity, number, polarity) triple in that sentence.
      6. Infer polarity from growth/decline verb lemmas; a sentence can
         carry multiple polarities (e.g. "three items added, two
         downgraded").
      7. Final filter: keep only entities that end up in >= 2 distinct
         facts, preserving the primitive's cross-sentence signal rule.

    Deterministic for a fixed spaCy model version. Python-only; no
    cross-language parity promise.
    """
    if not text:
        return ()

    doc = _nlp()(text)
    pairings = _extract_pairings(doc)
    if not pairings:
        return ()

    entity_counts = Counter(p.entity for p in pairings)
    return tuple(p for p in pairings if entity_counts[p.entity] >= 2)
