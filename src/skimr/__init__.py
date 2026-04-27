"""skimr — deterministic extractive summarization.

Public API:
  summarize(text, max_length, mode='default') -> SummaryResult
  brief(text, *, overview_max, max_facts, include_phrases, format) -> str | dict
  clean_text(text) -> str
  strip_think(text) -> str
  extract_keyword(text, keywords, num_sentences=10) -> str
  set_default_backend(name) -> None   # enrichment backend selector
"""
from skimr.clean import clean_text, strip_think
from skimr.tfidf import summarize
from skimr.brief import brief
from skimr.keyword import extract_keyword
from skimr._types import SummaryResult
from skimr.extract._backends import set_default_backend

__version__ = "0.2.1"
__all__ = [
    "summarize",
    "brief",
    "clean_text",
    "strip_think",
    "extract_keyword",
    "SummaryResult",
    "set_default_backend",
    "__version__",
]
