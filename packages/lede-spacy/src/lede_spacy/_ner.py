"""spaCy loader + entity extraction helpers.

The spaCy model is loaded lazily on first call. `warmup()` pre-loads it
to avoid a ~50ms surprise on the first real call.

Model selection: `_nlp()` defaults to ``en_core_web_sm`` (entities, lemma —
no vectors needed). Callers that need word vectors (``expand_hints(kinds=
("similar",))``) pass a vector-capable model, e.g. ``_nlp("en_core_web_md")``.
The default can be overridden with the ``LEDE_SPACY_MODEL`` env var. The cache
is keyed by model name so several models can coexist loaded.
"""
from __future__ import annotations
import os
from functools import lru_cache


_WANTED_LABELS = frozenset({"PERSON", "ORG", "GPE", "LOC", "PRODUCT"})

_DEFAULT_MODEL = "en_core_web_sm"


@lru_cache(maxsize=4)
def _nlp(model: str | None = None):
    """Return a cached spaCy nlp object for ``model``.

    ``model`` defaults to ``$LEDE_SPACY_MODEL`` or ``en_core_web_sm``. Raises
    ImportError if the requested model is not installed.
    """
    import spacy  # type: ignore[import-not-found]
    name = model or os.environ.get("LEDE_SPACY_MODEL", _DEFAULT_MODEL)
    try:
        return spacy.load(name)
    except OSError as e:
        raise ImportError(
            f"spaCy model {name!r} is missing. Install it with:\n"
            f"    python -m spacy download {name}"
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
