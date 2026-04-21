"""Hierarchical outline extractor.

Detects sections via structural heading patterns (markdown, allcaps,
short-colon-label). For each section picks the highest-composite-score
non-heading sentence as the representative.

Note: outline() uses a narrower heading predicate than _headings.is_heading
— it does NOT treat "fewer than 4 content tokens" as a heading signal,
because that heuristic misclassifies short body sentences as headings,
leaving sections with no representative-sentence candidates. Outline
needs real section structure, not title-length prose.

Mirrors rust/src/extract/outline.rs.
"""
import re

from .._headings import heading_name
from .._types import Section
from ..sentences import split_sentences
from ..tfidf import _composite_score_parts, _separate_heading_lines


_MD_HEADING_RE = re.compile(r"^\s*#+\s+.+$")
_ALLCAPS_RE = re.compile(r"^\s*[A-Z][A-Z\s]{3,28}:?\s*$")
_SHORT_LABEL_RE = re.compile(r"^\s*.{1,30}:\s*$")
_MD_DEPTH_RE = re.compile(r"^\s*(#+)\s+")


def _is_structural_heading(sentence: str) -> bool:
    """True when `sentence` matches a structural heading pattern.

    Narrower than `_headings.is_heading` — drops the "< 4 content tokens"
    fallback so short body sentences don't masquerade as headings.
    """
    if not sentence.strip():
        return False
    if _MD_HEADING_RE.match(sentence):
        return True
    if _ALLCAPS_RE.match(sentence):
        return True
    if _SHORT_LABEL_RE.match(sentence):
        return True
    return False


def _md_depth(heading_line: str) -> int:
    """Markdown heading depth (# = 1, ## = 2, ...). 1 for non-markdown headings."""
    m = _MD_DEPTH_RE.match(heading_line)
    if m:
        return len(m.group(1))
    return 1


def outline(text: str) -> tuple[Section, ...]:
    """Extract sections: heading + top-scoring non-heading sentence within."""
    if not text:
        return ()

    # Pre-split heading-only lines so they become standalone sentences —
    # mirrors tfidf.summarize's default-mode preprocessing.
    prepared = _separate_heading_lines(text)
    sentences = split_sentences(prepared)
    if not sentences:
        return ()

    parts = _composite_score_parts(sentences)
    scores = [0.60 * t + 0.25 * p + 0.15 * l for (t, p, l) in parts]

    # Group non-heading sentences under the most recent heading.
    sections: list[tuple[int, str, list[int]]] = []
    current: tuple[int, str, list[int]] | None = None
    for i, s in enumerate(sentences):
        if _is_structural_heading(s):
            if current is not None:
                sections.append(current)
            name = heading_name(s) or ""
            current = (_md_depth(s), name, [])
        else:
            if current is not None:
                current[2].append(i)
    if current is not None:
        sections.append(current)

    out: list[Section] = []
    for depth, name, body in sections:
        if not body or not name:
            continue
        best_idx = max(body, key=lambda i: scores[i])
        out.append(Section(
            depth=depth,
            name=name,
            representative_sentence=sentences[best_idx],
        ))
    return tuple(out)
