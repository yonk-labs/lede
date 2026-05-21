"""TF-IDF + position + length extractive summarization pipeline.

Composite score:
  score = 0.60 * tfidf + 0.25 * position + 0.15 * length

All scores normalized to [0, 1] per dimension. The composite is a weighted
sum, also in [0, 1].

v0.2.0 adds mode='default' with four scorer tweaks on top of the legacy
formula: heading filter, cue-phrase boost, digit bonus, and section-position
weighting. mode='legacy' preserves v0.0.1 behavior byte-identically. See
docs/v0-2-design.md for the design contract.
"""
import math
import re
from collections import Counter

from lede.sentences import split_sentences
from lede._headings import is_heading, heading_name
from lede._types import SummaryResult
from lede._hints import (
    preprocess_hints,
    hint_bonus,
    select_by_chars,
    round_to_int,
)

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

# --- v0.2 default-mode scorer tweaks ---

_CUE_PHRASE_RE = re.compile(
    r"^\s*(held|resolution|in summary|conclusion|action item|"
    r"decision|finding|key takeaway|outcome|ruling):?\b",
    re.IGNORECASE,
)

_DIGIT_RE = re.compile(r"\d+")

_SECTION_BOOST_HEADINGS = {
    "discussion", "conclusion", "held", "resolution",
    "key findings", "summary", "decision",
}


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
    """Length score: peaks in the 10-30 word range; penalizes shorter and longer."""
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


def _composite_score_parts(
    sentences: list[str],
) -> list[tuple[float, float, float]]:
    """Return (tfidf, position, length) triples per sentence."""
    if not sentences:
        return []
    t = tfidf_score(sentences)
    p = position_score(len(sentences))
    l = length_score(sentences)
    return [(t[i], p[i], l[i]) for i in range(len(sentences))]


def _composite_score_legacy(sentences: list[str]) -> list[float]:
    """Legacy composite: 0.60 * tfidf + 0.25 * position + 0.15 * length.

    Byte-identical to v0.0.1 behavior.
    """
    parts = _composite_score_parts(sentences)
    return [
        _TFIDF_WEIGHT * t + _POSITION_WEIGHT * p + _LENGTH_WEIGHT * l_
        for (t, p, l_) in parts
    ]


def composite_score(sentences: list[str]) -> list[float]:
    """Composite score: 0.60 * tfidf + 0.25 * position + 0.15 * length.

    Preserved for backward compatibility with callers and tests that import
    this helper directly. Equivalent to _composite_score_legacy.
    """
    return _composite_score_legacy(sentences)


def _separate_heading_lines(text: str) -> str:
    """Ensure heading-looking lines are separated from their following line by
    a blank line, so the sentence splitter treats them as standalone sentences.

    Only touches lines that the heading detector would classify as headings
    when considered in isolation. Idempotent: already-separated headings pass
    through unchanged.
    """
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i == len(lines) - 1:
            continue
        # If current line is a heading candidate and the next line is non-empty,
        # insert a blank line so paragraph-break splitting kicks in.
        if line.strip() and is_heading(line):
            nxt = lines[i + 1]
            if nxt.strip():
                out.append("")
    return "\n".join(out)


def _build_section_map(sentences: list[str]) -> dict[int, str]:
    """Map each sentence index to the lowercase name of the most recent
    heading above it (or "" if none)."""
    section_map: dict[int, str] = {}
    current = ""
    for i, sentence in enumerate(sentences):
        if is_heading(sentence):
            name = heading_name(sentence)
            current = name.lower() if name else ""
        section_map[i] = current
    return section_map


def _composite_score_default(
    sentences: list[str],
    section_map: dict[int, str],
) -> list[float]:
    """v0.2 default scorer: legacy composite + four tweaks.

    - Heading sentences get -inf (dropped from selection).
    - Sentences under a high-signal section (discussion/conclusion/etc.)
      get tfidf *= 1.3.
    - Cue-phrase sentences ("Held:", "Resolution:", ...) get +2.0.
    - Sentences containing digits get +0.3.
    """
    parts = _composite_score_parts(sentences)
    scores: list[float] = []
    for i, sentence in enumerate(sentences):
        if is_heading(sentence):
            scores.append(float("-inf"))
            continue
        t, p, l_ = parts[i]
        if section_map.get(i, "") in _SECTION_BOOST_HEADINGS:
            t *= 1.3
        score = _TFIDF_WEIGHT * t + _POSITION_WEIGHT * p + _LENGTH_WEIGHT * l_
        if _CUE_PHRASE_RE.match(sentence):
            score += 2.0
        if _DIGIT_RE.search(sentence):
            score += 0.3
        scores.append(score)
    return scores


# --- Top-level summarize pipeline ---

_MIN_SENTENCES = 3
_MIN_BUDGET_FOR_SENTENCES = 50  # chars; below this, truncate


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    # Reserve 3 chars for the ellipsis
    body_budget = max(0, max_length - 3)
    return text[:body_budget] + "..."


def _summarize_legacy(text: str, max_length: int = 500) -> str:
    """Extractive summary — v0.0.1 byte-identical behavior.

    Pipeline:
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

    scores = _composite_score_legacy(sentences)
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


def _summarize_with_hints(
    text: str,
    max_length: int,
    *,
    mode: str,
    hints: list[tuple[str, float]],
    hint_focus: float,
    hint_mode: str,
) -> str:
    """Two-pool selection: hint pool (bonus-augmented or hard-filtered) + plain pool."""
    if not text:
        return ""
    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return _truncate(text, max_length)

    prepared = _separate_heading_lines(text)
    sentences = split_sentences(prepared)
    if len(sentences) < _MIN_SENTENCES:
        if len(text) <= max_length:
            return text
        return _truncate(text, max_length)

    section_map = _build_section_map(sentences)
    if mode == "coverage":
        from lede.coverage import _composite_score_coverage_for_hints  # added in T5
        plain_scores = _composite_score_coverage_for_hints(sentences)
    else:
        plain_scores = _composite_score_default(sentences, section_map)

    # Hint-pool scores. Soft = plain + bonus. Hard = -inf when no match.
    bonuses = [hint_bonus(s, hints) for s in sentences]
    if hint_mode == "hard":
        hint_scores = [
            (plain_scores[i] + bonuses[i]) if bonuses[i] > 0 else float("-inf")
            for i in range(len(sentences))
        ]
    else:  # soft
        hint_scores = [plain_scores[i] + bonuses[i] for i in range(len(sentences))]

    lengths = [len(s) for s in sentences]
    hint_budget = round_to_int(max_length, hint_focus)
    normal_budget = max_length - hint_budget

    selected_hint = select_by_chars(
        hint_scores, lengths, budget=hint_budget, exclude=set()
    )
    selected_normal = select_by_chars(
        plain_scores, lengths, budget=normal_budget, exclude=selected_hint
    )

    # Rollover: unused hint budget → plain pool.
    # In hard mode, rollover still respects the hard filter (uses hint_scores so
    # -inf sentences stay ineligible). In soft mode, plain_scores allow any sentence.
    used_hint = sum(lengths[i] for i in selected_hint) + max(0, len(selected_hint) - 1)
    unused_hint = hint_budget - used_hint
    if unused_hint > 0:
        rollover_scores = hint_scores if hint_mode == "hard" else plain_scores
        extra = select_by_chars(
            rollover_scores,
            lengths,
            budget=unused_hint,
            exclude=selected_hint | selected_normal,
        )
        selected_normal |= extra

    # Soft-only rollover: unused normal → hint pool.
    used_normal = sum(lengths[i] for i in selected_normal) + max(0, len(selected_normal) - 1)
    unused_normal = normal_budget - used_normal
    if unused_normal > 0 and hint_mode == "soft":
        extra = select_by_chars(
            hint_scores,
            lengths,
            budget=unused_normal,
            exclude=selected_hint | selected_normal,
        )
        selected_hint |= extra

    selected = sorted(selected_hint | selected_normal)
    if not selected:
        return _truncate(text, max_length)
    return " ".join(sentences[i] for i in selected)


def _summarize_default(text: str, max_length: int = 500) -> str:
    """v0.2 default scorer — mirrors _summarize_legacy with the default scorer.

    Headings are dropped from candidates (score = -inf), cue-phrase sentences
    are boosted by +2.0, digit-bearing sentences get +0.3, and sentences
    under high-signal section headings have tfidf * 1.3.

    Unlike legacy mode, default mode always runs the sentence pipeline when
    the budget allows it (>= _MIN_BUDGET_FOR_SENTENCES) so headings are
    filtered even when the raw input would otherwise fit.
    """
    if not text:
        return ""

    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return _truncate(text, max_length)

    # Pre-split heading-only lines so they become standalone sentences
    # and can be individually filtered by the heading detector.
    prepared = _separate_heading_lines(text)
    sentences = split_sentences(prepared)
    if len(sentences) < _MIN_SENTENCES:
        if len(text) <= max_length:
            return text
        return _truncate(text, max_length)

    section_map = _build_section_map(sentences)
    scores = _composite_score_default(sentences, section_map)
    indices_by_score = sorted(
        range(len(sentences)),
        key=lambda i: (-scores[i], i),
    )

    selected: list[int] = []
    used = 0
    separator = " "
    for idx in indices_by_score:
        # Skip headings / dropped candidates entirely.
        if scores[idx] == float("-inf"):
            continue
        sentence = sentences[idx]
        needed = len(sentence) + (len(separator) if selected else 0)
        if used + needed <= max_length:
            selected.append(idx)
            used += needed

    if not selected:
        return _truncate(text, max_length)

    selected.sort()
    return separator.join(sentences[i] for i in selected)


_ATTACH_KEYS = {"stats", "outline", "metadata", "phrases", "correlated_facts"}


def summarize(
    text: str,
    max_length: int = 500,
    *,
    mode: str = "default",
    attach: list[str] | tuple[str, ...] | None = None,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
) -> SummaryResult:
    """Extractive summary with configurable scoring mode and optional hints.

    Args:
        text: input document text.
        max_length: character budget for the output summary. Default 500.
        mode: scoring mode — ``"default"`` (TF-IDF + position + length,
            heading-filtered), ``"legacy"`` (pre-v0.2 byte-identical scorer),
            or ``"coverage"`` (paragraph-aware selection). Default
            ``"default"``.
        attach: list of extra primitives to attach to the returned
            ``SummaryResult``. Supported names: ``"stats"``, ``"outline"``,
            ``"metadata"``, ``"phrases"``, ``"correlated_facts"``.
        hints: optional list[str] or dict[str, float] of terms to bias
            selection toward. List entries get weight 1.0; dict keys are
            terms and values are numeric weights. Default None (no biasing).
        hint_focus: fraction of the character budget reserved for
            hint-matching sentences. Range [0.0, 1.0]. Default 0.7 — 70 %
            of budget goes to hint-matching sentences first, remaining 30 %
            to the highest-scored non-hint sentences. Unused hint-pool budget
            rolls over to the plain pool (and vice versa in soft mode).
            Ignored when ``hints`` is None.
        hint_mode: biasing strategy — ``"soft"`` (default) or ``"hard"``.
            ``"soft"`` adds a bonus to hint-matching sentences and reorders
            without filtering; non-matching sentences can still appear.
            ``"hard"`` restricts the hint pool to only sentences that match
            at least one hint; unmatched sentences can still appear in the
            plain-pool quota. Ignored when ``hints`` is None.

    Returns:
        ``SummaryResult`` — a frozen dataclass with ``.summary: str`` plus
        optional fields populated by ``attach``.  ``str(r)`` and ``f"{r}"``
        evaluate to ``.summary`` so legacy string callers still work.

    Raises:
        ValueError: on unknown ``mode``, on ``mode="legacy"`` with hints
            (not supported), on ``hint_focus`` outside [0.0, 1.0], or on
            unknown ``hint_mode``.

    Hint biasing (v0.4):
        When ``hints`` is None (the default), no new code path executes and
        output is byte-identical to v0.3.0. Matching is case-insensitive
        and word-boundary-delimited (``\\b``); no Unicode normalization or
        stemming. For lemma/synonym expansion, compose with
        ``lede_spacy.expand_hints`` before passing hints here::

            from lede import summarize
            from lede_spacy import expand_hints

            expanded = expand_hints(["counties"], kinds=("lemma",))
            # expanded == ["counties", "county"]
            result = summarize(text, hints=expanded, hint_focus=0.7).summary

        Simple usage without expansion::

            from lede import summarize
            result = summarize(text, hints=["John Smith", "county"], hint_focus=0.7).summary

        See docs/REFERENCE.md "Hint biasing" for the full contract.
    """
    # Validate hint kwargs first (before any work).
    processed_hints = preprocess_hints(hints)
    if processed_hints:
        if mode not in ("default", "coverage", "legacy"):
            raise ValueError(f"unknown mode: {mode!r}")
        if not 0.0 <= hint_focus <= 1.0:
            raise ValueError(
                f"hint_focus must be in [0.0, 1.0]; got {hint_focus}"
            )
        if hint_mode not in ("soft", "hard"):
            raise ValueError(
                f"hint_mode must be 'soft' or 'hard'; got {hint_mode!r}"
            )
        if mode == "legacy":
            raise ValueError("hints not supported in legacy mode")
        summary_text = _summarize_with_hints(
            text,
            max_length=max_length,
            mode=mode,
            hints=processed_hints,
            hint_focus=hint_focus,
            hint_mode=hint_mode,
        )
    elif mode == "coverage":
        from lede.coverage import summarize_coverage
        summary_text = summarize_coverage(text, max_length=max_length)
    elif mode == "legacy":
        summary_text = _summarize_legacy(text, max_length=max_length)
    elif mode == "default":
        summary_text = _summarize_default(text, max_length=max_length)
    else:
        raise ValueError(f"unknown mode: {mode!r}")

    kwargs: dict = {}
    if attach:
        unknown = set(attach) - _ATTACH_KEYS
        if unknown:
            raise ValueError(f"unknown attach key(s): {sorted(unknown)}")
        from lede.extract import stats as _stats
        from lede.extract import outline as _outline
        from lede.extract import metadata as _metadata
        from lede.extract import phrases as _phrases
        from lede.extract import correlate_facts as _correlate
        if "stats" in attach:
            kwargs["stats"] = tuple(_stats(text))
        if "outline" in attach:
            kwargs["outline"] = tuple(_outline(text))
        if "metadata" in attach:
            kwargs["metadata"] = _metadata(text)
        if "phrases" in attach:
            kwargs["phrases"] = tuple(_phrases(text))
        if "correlated_facts" in attach:
            kwargs["correlated_facts"] = tuple(_correlate(text))
    return SummaryResult(summary=summary_text, **kwargs)
