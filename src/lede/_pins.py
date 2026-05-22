"""v0.4.2 heading/pin retention helpers (pure, deterministic).

Locates headings by index in a sentence list and renders pinned content.
Reuses lede._headings for all "what is a heading" logic; adds no new
heading detection. The Rust mirror is rust/src/pins.rs.
"""
from __future__ import annotations

from lede._headings import is_structural_heading, heading_name, md_depth


def nearest_heading_map(sentences: list[str]) -> list[int | None]:
    """For each sentence index, the index of the most recent heading
    sentence at or before it, or None if no heading precedes it.

    A heading's own entry is None (headings are never selected, so the
    value is unused; None keeps the rule "the heading above me")."""
    out: list[int | None] = []
    current: int | None = None
    for i, s in enumerate(sentences):
        if is_structural_heading(s):
            out.append(None)
            current = i
        else:
            out.append(current)
    return out


def document_title_index(sentences: list[str]) -> int | None:
    """Index of the document title: a depth-1 heading appearing before
    any body sentence. None if the first sentence-ish line is body, or
    the first heading is not markdown depth 1."""
    for i, s in enumerate(sentences):
        if is_structural_heading(s):
            return i if md_depth(s) == 1 else None
        return None
    return None


def render_toc(text: str) -> str:
    """Render a table of contents from the document outline. Each
    section name on its own line, indented (depth-1)*2 spaces."""
    from lede.extract.outline import outline

    lines: list[str] = []
    for section in outline(text):
        indent = "  " * max(0, section.depth - 1)
        lines.append(f"{indent}{section.name}")
    return "\n".join(lines)
