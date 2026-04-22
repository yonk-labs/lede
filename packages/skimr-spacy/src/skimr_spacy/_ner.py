"""spaCy loader + entity extraction helpers.

The spaCy model is loaded lazily on first call. `warmup()` pre-loads it
to avoid a ~50ms surprise on the first real call.
"""
from __future__ import annotations
from functools import lru_cache


_WANTED_LABELS = frozenset({"PERSON", "ORG", "GPE", "LOC", "PRODUCT"})


@lru_cache(maxsize=1)
def _nlp():
    """Return the cached spaCy nlp object. Raises ImportError if missing."""
    import spacy  # type: ignore[import-not-found]
    try:
        return spacy.load("en_core_web_sm")
    except OSError as e:
        raise ImportError(
            "spaCy is installed but en_core_web_sm is missing. "
            "Reinstall skimr-spacy to pull it in automatically, or run:\n"
            "    python -m spacy download en_core_web_sm"
        ) from e


def extract_entities(text: str) -> tuple[str, ...]:
    """Return unique PERSON/ORG/GPE/LOC/PRODUCT surface forms in first-appearance order."""
    if not text:
        return ()
    doc = _nlp()(text)
    seen: set[str] = set()
    out: list[str] = []
    for ent in doc.ents:
        if ent.label_ in _WANTED_LABELS:
            s = ent.text.strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return tuple(out)


def warmup() -> None:
    """Pre-load the spaCy model so the first metadata() call is fast."""
    _ = _nlp()
