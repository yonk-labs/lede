"""skimr-spacy — spaCy-powered entity and phrase extraction for skimr.

Importing this package registers the 'spacy' backend for skimr's
enrichment primitives. After import:
  - skimr.extract.metadata(text, backend='spacy') populates Metadata.entities
  - skimr.extract.phrases(text, backend='spacy') uses syntactic noun_chunks
"""
from skimr.extract._backends import register
from ._metadata import spacy_metadata
from ._ner import extract_entities, warmup
from ._phrases import spacy_phrases

# Side-effect: register all spacy backends with skimr on import.
register("spacy", "metadata", spacy_metadata)
register("spacy", "phrases", spacy_phrases)

__version__ = "0.2.0.dev0"
__all__ = [
    "extract_entities",
    "spacy_phrases",
    "warmup",
    "__version__",
]
