"""lede — deterministic extractive summarization.

Public API:
  summarize(text, max_length, mode='default') -> SummaryResult
  brief(text, *, overview_max, max_facts, include_phrases, format) -> str | dict
  clean_text(text) -> str
  strip_think(text) -> str
  extract_keyword(text, keywords, num_sentences=10) -> str
  set_default_backend(name) -> None   # enrichment backend selector
  format_extract(kind, value, output='text') -> str
  format_result(value, output='text') -> str
"""
from lede.clean import clean_text, strip_think
from lede.tfidf import summarize
from lede.brief import brief
from lede.keyword import extract_keyword
from lede._types import SummaryResult
from lede.extract._backends import set_default_backend
from lede.format import format_extract, format_result, to_data, to_json

__version__ = "0.4.3"
__all__ = [
    "summarize",
    "brief",
    "clean_text",
    "strip_think",
    "extract_keyword",
    "SummaryResult",
    "set_default_backend",
    "format_extract",
    "format_result",
    "to_data",
    "to_json",
    "__version__",
]
