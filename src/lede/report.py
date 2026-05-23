"""Readable combined reports over lede core and optional spaCy extraction."""
from __future__ import annotations

from collections.abc import Sequence

from ._types import ReadableReport
from .tfidf import summarize
from .extract import correlate_facts, key_facts, metadata, phrases, stats


def _register_spacy_if_requested(backend: str) -> bool:
    if backend not in ("spacy", "auto"):
        return False
    try:
        import lede_spacy  # noqa: F401  # side-effect: registers backend
        return True
    except ImportError as e:
        if backend == "spacy":
            raise ImportError(
                "readable_report(backend='spacy') requires lede-spacy. Install with:\n"
                "    pip install lede-spacy\n"
                "    python -m spacy download en_core_web_sm"
            ) from e
        return False


def readable_report(
    text: str,
    *,
    max_length: int = 2000,
    max_facts: int = 40,
    mode: str = "default",
    backend: str = "regex",
    include_toc: bool = True,
    keep_headings: bool = True,
    headings: Sequence[str] | None = None,
    pin: Sequence[str] | None = None,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
    convert_word_names: bool = False,
) -> ReadableReport:
    """Build a readable report combining lede summary/facts and optional spaCy details.

    The default is tuned for human and agent inspection: a 2000-character
    lede summary with headings/TOC retained, up to 40 lede key facts, regex
    metadata/stats, and spaCy-backed entities / entity-number correlations
    only when requested with backend="spacy" or backend="auto".
    """
    spacy_available = _register_spacy_if_requested(backend)

    summary = summarize(
        text,
        max_length=max_length,
        mode=mode,
        keep_headings=keep_headings,
        include_toc=include_toc,
        headings=headings,
        pin=pin,
        hints=hints,
        hint_focus=hint_focus,
        hint_mode=hint_mode,
    )

    lede_stats = stats(text, convert_word_names=convert_word_names)
    lede_metadata = metadata(text, backend="regex")
    lede_facts = key_facts(
        text,
        max_facts=max_facts,
        convert_word_names=convert_word_names,
        hints=hints,
        hint_focus=hint_focus,
        hint_mode=hint_mode,
    )

    spacy_metadata = None
    spacy_facts = ()
    spacy_phrases = ()
    if spacy_available:
        try:
            spacy_metadata = metadata(text, backend="spacy")
            spacy_facts = correlate_facts(text, backend="spacy")
            spacy_phrases = phrases(text, backend="spacy")
        except (ImportError, TypeError):
            if backend == "spacy":
                raise

    return ReadableReport(
        summary=summary,
        key_facts=lede_facts,
        stats=lede_stats,
        metadata=lede_metadata,
        spacy_metadata=spacy_metadata,
        spacy_facts=spacy_facts,
        spacy_phrases=spacy_phrases,
    )
