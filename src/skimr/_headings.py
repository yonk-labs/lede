"""Shared heading detection.

Any sentence matching any of these patterns is considered a heading and is
dropped from candidate selection in mode='default'. Also used by
extract.outline to discover section names.
"""
import re

# Markdown ATX-style heading: one or more # followed by space and text
_MD_HEADING_RE = re.compile(r"^\s*#+\s+.+$")

# ALL-CAPS short line: 4-30 chars of A-Z/space/colon, no lowercase
_ALLCAPS_RE = re.compile(r"^\s*[A-Z][A-Z\s]{3,28}:?\s*$")

# Short label ending in colon (<=30 chars including the colon)
_SHORT_LABEL_RE = re.compile(r"^\s*.{1,30}:\s*$")


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
    # Strip markdown #'s and trailing colon.
    s = re.sub(r"^#+\s+", "", s)
    s = s.rstrip(":").strip()
    if not s:
        return None
    return s
