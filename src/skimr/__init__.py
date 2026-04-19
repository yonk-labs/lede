"""skimr — deterministic extractive summarization.

Public API:
  summarize(text, max_length, mode='tfidf', **kwargs) -> str
  clean_text(text) -> str
  strip_think(text) -> str
  extract_keyword(text, keywords, num_sentences=10) -> str
"""
try:
    from skimr.clean import clean_text, strip_think
    from skimr.tfidf import summarize
    from skimr.keyword import extract_keyword
except ModuleNotFoundError:
    # Submodules are being added incrementally (Tasks 3-7). Allow individual
    # submodule imports to succeed before the full public API is wired up.
    pass

__version__ = "0.0.1"
__all__ = ["summarize", "clean_text", "strip_think", "extract_keyword", "__version__"]
