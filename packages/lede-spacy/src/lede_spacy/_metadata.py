"""spaCy-backed implementation of lede's metadata primitive.

Delegates date/amount/URL extraction to lede's regex backend (via the
public `backend='regex'` path) to guarantee identical core-field behavior,
then augments `Metadata.entities` via spaCy NER.
"""
from __future__ import annotations
import dataclasses
from lede._types import Metadata
from lede.extract import metadata as _lede_metadata
from ._ner import extract_entities


def spacy_metadata(text: str) -> Metadata:
    """Full metadata extraction with spaCy entities.

    Uses lede's regex path for the deterministic fields (dates, amounts, urls)
    so core output remains identical to backend='regex'. Adds entities on top.
    """
    base = _lede_metadata(text, backend="regex")
    return dataclasses.replace(base, entities=extract_entities(text))
