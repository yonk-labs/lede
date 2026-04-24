"""Shared heading detection.

Any sentence matching any of these patterns is considered a heading and is
dropped from candidate selection in mode='default'. Also used by
extract.outline to discover section names.
"""
import re

# Markdown ATX-style heading: one or more # followed by space and text
_MD_HEADING_RE = re.compile(r"^\s*#+\s+.+$")

# ALL-CAPS short line: 4-80 chars of A-Z/space/colon, no lowercase.
# Upper bound extended from 28 -> 80 in T13b so long document-title
# conventions like "SUPREME COURT OF THE UNITED STATES" (32 chars) match.
_ALLCAPS_RE = re.compile(r"^\s*[A-Z][A-Z\s]{3,80}:?\s*$")

# Short label ending in colon (<=30 chars including the colon)
_SHORT_LABEL_RE = re.compile(r"^\s*.{1,30}:\s*$")

# Bare title-case single-line heading (T13b Class A): starts uppercase,
# second char alphanumeric (not space/punct), up to ~60 chars total, no
# internal special chars, no terminal punctuation. Matches bare lines like
# "Abstract", "Introduction", "Modern methods", "Privacy Policy".
#
# The "no terminal punctuation" constraint is load-bearing: it excludes short
# body sentences like "Costs declined." that ended in a period, which was the
# T6 false-positive class we dropped the < 4 content-tokens fallback for.
_BARE_TITLE_RE = re.compile(r"^\s*[A-Z][A-Za-z0-9][A-Za-z0-9 ]{0,58}$")

# Numbered-section-prefix heading (T13b Class B): "\d+. Section Name" on its
# own line. Matches "1. Information We Collect" etc. The numeric prefix is
# stripped by `heading_name()` so the emitted name matches gold.
_NUMBERED_SECTION_RE = re.compile(r"^\s*\d+\.\s+[A-Z][A-Za-z0-9 ]{0,58}$")


def is_heading(sentence: str) -> bool:
    """True when `sentence` matches any heading pattern."""
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
    # Fewer than 4 content-word tokens (rough "title-like" filter).
    toks = [t for t in re.findall(r"[A-Za-z]{3,}", sentence)]
    if len(toks) < 4:
        return True
    return False


def heading_name(sentence: str) -> str | None:
    """Extract the name portion of a heading, or None if not a heading."""
    s = sentence.strip()
    if not s:
        return None
    # Strip markdown #'s, numeric-section prefix, and trailing colon.
    s = re.sub(r"^#+\s+", "", s)
    s = re.sub(r"^\d+\.\s+", "", s)
    s = s.rstrip(":").strip()
    if not s:
        return None
    return s
