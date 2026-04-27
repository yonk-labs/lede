"""extract.metadata — stdlib core + pluggable backend dispatch.

Core path (always available):
  - dates: ISO yyyy-mm-dd and US m/d/yyyy
  - amounts: money patterns (similar shape to extract.stats, defined locally)
  - urls: http(s) URLs

Backend selection:
  - backend='regex' (default): zero-dep stdlib regex path. entities always ().
  - backend='spacy': requires the skimr-spacy companion package; it registers
    itself on import and populates entities via en_core_web_sm.
  - backend='auto': spacy if registered, else regex.
  - backend=None: use the process-wide default (skimr.set_default_backend).

See docs/superpowers/specs/2026-04-21-skimr-spacy-integration.md.
"""
import re
from .._types import Metadata
from . import _backends


# Date patterns mirror extract.stats._DATE_RE: ISO yyyy-mm-dd, US m/d/yyyy,
# and bare years 1900-2099. Same shape, same bounds, same parity contract.
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:19|20)\d{2}\b"
)
# Amount quantifiers bounded {0,18} for ReDoS parity with extract.stats._MONEY_RE.
_AMOUNT_RE = re.compile(
    r"\$\d[\d,]{0,18}(?:\.\d{1,4})?[KMB]?|\d[\d,]{0,18}(?:\.\d{1,4})?\s*(?:dollars?|USD|EUR|GBP|JPY|CHF)",
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


def _regex_metadata(text: str) -> Metadata:
    """Regex backend: zero-dep core path. entities always ()."""
    if not text:
        return Metadata()
    return Metadata(
        dates=_collect_unique(_DATE_RE, text),
        amounts=_collect_unique(_AMOUNT_RE, text),
        urls=_collect_unique(_URL_RE, text),
        entities=(),
    )


# Regex backend self-registers at module load so it is always available.
_backends.register("regex", "metadata", _regex_metadata)


def metadata(text: str, *, backend: str | None = None) -> Metadata:
    """Core metadata + optional neural entities via backend= kwarg.

    backend='regex' (default): zero-dep regex path. Populates dates/amounts/urls;
        entities always empty.
    backend='spacy': requires skimr-spacy installed. Populates entities too.
    backend='auto': spacy if registered else regex.
    backend=None: uses the global default (skimr.set_default_backend).
    """
    if backend is None:
        backend = _backends.get_default_backend()
    impl = _backends.resolve(backend, "metadata")
    return impl(text)
