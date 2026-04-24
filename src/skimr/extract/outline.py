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
# ALLCAPS upper bound widened to 80 (T13b Class C) for long title
# conventions like "SUPREME COURT OF THE UNITED STATES".
_ALLCAPS_RE = re.compile(r"^\s*[A-Z][A-Z\s]{3,80}:?\s*$")
_SHORT_LABEL_RE = re.compile(r"^\s*.{1,30}:\s*$")
# Bare title-case heading (T13b Class A). Terminal-punctuation exclusion
# prevents re-introducing the T6 "Costs declined." false-positive class.
_BARE_TITLE_RE = re.compile(r"^\s*[A-Z][A-Za-z0-9][A-Za-z0-9 ]{0,58}$")
# Numbered-section prefix (T13b Class B); numeric prefix stripped by
# `heading_name()` in _headings.py so emitted name matches gold.
_NUMBERED_SECTION_RE = re.compile(r"^\s*\d+\.\s+[A-Z][A-Za-z0-9 ]{0,58}$")
_MD_DEPTH_RE = re.compile(r"^\s*(#+)\s+")

# T13b Class D cases intentionally NOT handled here (need gold-protocol
# revisit, tracked as T13d):
#   - "Meeting: Platform Migration Planning" (Label:Subject inline pattern)
#   - "Held: Section 412(b) does not authorize..." (inline colon-label with
#     body text after the colon on the same line; adding a pattern broad
#     enough to match it without firing on every prose "So: this is..."
#     requires conversation with gold protocol)
#   - "Reply from support (Kai T., day 1)" (parenthetical structured
#     heading; too corpus-specific for a general predicate)


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
    if _BARE_TITLE_RE.match(sentence):
        return True
    if _NUMBERED_SECTION_RE.match(sentence):
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
