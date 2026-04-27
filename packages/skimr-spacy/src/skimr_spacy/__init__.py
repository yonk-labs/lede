"""skimr-spacy — spaCy-powered entity and phrase extraction for skimr.

Importing this package registers the 'spacy' backend for skimr's
enrichment primitives. After import:
  - skimr.extract.metadata(text, backend='spacy') populates Metadata.entities
  - skimr.extract.phrases(text, backend='spacy') uses syntactic noun_chunks
"""
from skimr.extract._backends import register
from ._correlate import spacy_correlate_facts
from ._metadata import spacy_metadata
from ._ner import extract_entities, warmup
from ._phrases import spacy_phrases

# Side-effect: register all spacy backends with skimr on import.
register("spacy", "metadata", spacy_metadata)
register("spacy", "phrases", spacy_phrases)
register("spacy", "correlate_facts", spacy_correlate_facts)

__version__ = "0.2.1"
__all__ = [
    "extract_entities",
    "spacy_correlate_facts",
    "spacy_phrases",
    "warmup",
    "__version__",
]
