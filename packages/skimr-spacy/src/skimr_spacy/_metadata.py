"""spaCy-backed implementation of skimr's metadata primitive.

Delegates date/amount/URL extraction to skimr's regex backend (via the
public `backend='regex'` path) to guarantee identical core-field behavior,
then augments `Metadata.entities` via spaCy NER.
"""
from __future__ import annotations
import dataclasses
from skimr._types import Metadata
from skimr.extract import metadata as _skimr_metadata
from ._ner import extract_entities


def spacy_metadata(text: str) -> Metadata:
    """Full metadata extraction with spaCy entities.

    Uses skimr's regex path for the deterministic fields (dates, amounts, urls)
    so core output remains identical to backend='regex'. Adds entities on top.
    """
    base = _skimr_metadata(text, backend="regex")
    return dataclasses.replace(base, entities=extract_entities(text))
