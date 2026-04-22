"""skimr-spacy — spaCy-powered entity extraction for skimr.

Importing this package registers the 'spacy' backend for skimr's enrichment
primitives. After import, `skimr.extract.metadata(text, backend='spacy')`
populates `Metadata.entities` using spaCy's en_core_web_sm NER model.
"""
from skimr.extract._backends import register
from ._metadata import spacy_metadata
from ._ner import extract_entities, warmup

# Side-effect: register the 'spacy' backend with skimr's registry on import.
register("spacy", "metadata", spacy_metadata)

__version__ = "0.2.0.dev0"
__all__ = [
    "extract_entities",
    "warmup",
    "__version__",
]
