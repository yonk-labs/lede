"""extract.metadata — stdlib core + optional NER enhancement.

Core path (always available):
  - dates: ISO yyyy-mm-dd and US m/d/yyyy
  - amounts: money patterns (similar shape to extract.stats, defined locally)
  - urls: http(s) URLs

NER path (installed via `skimr[ner]`):
  - entities: PERSON / ORG / GPE via spaCy en_core_web_sm

Task 8 = core only. Task 9 wires NER.
"""
import re
from .._types import Metadata


_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
)
_AMOUNT_RE = re.compile(
    r"\$\d[\d,]*(?:\.\d+)?[KMB]?|\d[\d,]*(?:\.\d+)?\s*(?:dollars?|USD|EUR|GBP|JPY|CHF)",
    re.IGNORECASE,
)
_URL_RE = re.compile(
    r"https?://[^\s<>\"')]+",
    re.IGNORECASE,
)


def _collect_unique(regex: re.Pattern, text: str) -> tuple[str, ...]:
    """Find all matches preserving first-appearance order, deduped."""
    seen: set[str] = set()
    out: list[str] = []
    for m in regex.finditer(text):
        v = m.group(0)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return tuple(out)


def metadata(text: str) -> Metadata:
    """Core metadata extraction. Entities are empty; see skimr[ner]."""
    if not text:
        return Metadata()
    return Metadata(
        dates=_collect_unique(_DATE_RE, text),
        amounts=_collect_unique(_AMOUNT_RE, text),
        urls=_collect_unique(_URL_RE, text),
        entities=(),  # NER populates this in Task 9 when installed
    )
