"""lede-spacy — spaCy-powered entity and phrase extraction for lede.

Importing this package registers the 'spacy' backend for lede's
enrichment primitives. After import:
  - lede.extract.metadata(text, backend='spacy') populates Metadata.entities
  - lede.extract.phrases(text, backend='spacy') uses syntactic noun_chunks
"""
from lede.extract._backends import register
from ._correlate import spacy_correlate_facts
from ._expand import expand_hints
from ._metadata import spacy_metadata
from ._ner import extract_entities, warmup
from ._phrases import spacy_phrases

# Side-effect: register all spacy backends with lede on import.
register("spacy", "metadata", spacy_metadata)
register("spacy", "phrases", spacy_phrases)
register("spacy", "correlate_facts", spacy_correlate_facts)

__version__ = "0.3.0"
__all__ = [
    "expand_hints",
    "extract_entities",
    "spacy_correlate_facts",
    "spacy_phrases",
    "warmup",
    "__version__",
]
