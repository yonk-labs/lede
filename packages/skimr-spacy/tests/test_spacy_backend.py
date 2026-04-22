"""Tests for the skimr-spacy companion package."""
import pytest

# Guard: skip the entire module if spaCy or the model is unavailable at import.
spacy = pytest.importorskip("spacy")
try:
    spacy.load("en_core_web_sm")
except OSError:
    pytest.skip("en_core_web_sm not installed", allow_module_level=True)


# Importing skimr_spacy must happen AFTER the skip guards so a clean
# skip message surfaces when the env lacks the model.
import skimr_spacy  # noqa: E402  — import-for-side-effect: registers 'spacy' backend
from skimr.extract import metadata, phrases  # noqa: E402
from skimr.extract._backends import resolve  # noqa: E402
from skimr_spacy import spacy_phrases  # noqa: E402,F401


def test_skimr_spacy_registers_on_import():
    fn = resolve("spacy", "metadata")
    assert callable(fn)


def test_spacy_backend_populates_entities():
    m = metadata(
        "Sarah Jones visited Johnson Education Co in Chicago last Tuesday.",
        backend="spacy",
    )
    ents_lower = [e.lower() for e in m.entities]
    assert any("sarah" in e for e in ents_lower)
    assert any("johnson" in e for e in ents_lower)
    assert any("chicago" in e for e in ents_lower)


def test_spacy_backend_preserves_core_fields():
    """spaCy backend must produce the same dates/amounts/urls as regex."""
    text = "Sarah signed the contract 2025-06-14 for $120K. See https://example.com/docs."
    regex_m = metadata(text, backend="regex")
    spacy_m = metadata(text, backend="spacy")
    assert regex_m.dates == spacy_m.dates
    assert regex_m.amounts == spacy_m.amounts
    assert regex_m.urls == spacy_m.urls
    # entities: regex empty, spacy populated
    assert regex_m.entities == ()
    assert spacy_m.entities  # non-empty


def test_auto_backend_picks_spacy_after_import():
    m = metadata(
        "Sarah Jones visited Johnson Education Co.",
        backend="auto",
    )
    # After skimr_spacy is imported, auto prefers spacy
    assert m.entities  # non-empty — proves spacy ran, not regex


def test_warmup_is_callable():
    from skimr_spacy import warmup
    warmup()  # must not raise
    # Subsequent call benefits from cached model
    m = metadata("Stripe closed a deal with OpenAI.", backend="spacy")
    assert len(m.entities) >= 1


def test_empty_text_spacy_backend():
    m = metadata("", backend="spacy")
    assert m.dates == ()
    assert m.amounts == ()
    assert m.urls == ()
    assert m.entities == ()


# --- T10b: spacy_phrases tests ---


def test_spacy_phrases_registers_on_import():
    fn = resolve("spacy", "phrases")
    assert callable(fn)


def test_spacy_phrases_extracts_noun_chunks():
    text = (
        "The customer support team evaluated the deployment pipeline. "
        "The deployment pipeline is critical to the customer support team."
    )
    r = phrases(text, backend="spacy")
    joined = " | ".join(r).lower()
    # spaCy's noun_chunker should surface multi-word noun phrases
    assert r  # non-empty
    # At least one of the obvious noun phrases should appear
    assert any(p in joined for p in (
        "customer support team",
        "deployment pipeline",
    ))


def test_spacy_phrases_keywords_include_hits():
    # With keywords, singleton multi-word noun phrases containing the keyword surface.
    # Input chosen so spaCy emits multi-word noun chunks (single-word chunks are
    # filtered by the "< 2 tokens" rule and cannot reach the keyword path).
    text = (
        "The revenue forecast improved sharply. "
        "The cost structure held steady. "
        "The margin profile widened."
    )
    r = phrases(text, keywords="revenue", backend="spacy")
    # Should have at least one phrase mentioning revenue (even though it's a singleton)
    lowered = [p.lower() for p in r]
    assert any("revenue" in p for p in lowered), f"got: {r}"


def test_spacy_phrases_empty_input():
    assert phrases("", backend="spacy") == ()


def test_auto_backend_picks_spacy_phrases_after_import():
    # Since skimr_spacy is imported at module top, auto should dispatch to spacy
    text = (
        "The customer support team evaluated the deployment pipeline. "
        "The deployment pipeline is critical to the customer support team."
    )
    regex_out = phrases(text, backend="regex")
    auto_out = phrases(text, backend="auto")
    # auto resolves to spacy in this test environment -> different from regex
    # (we can't assert exact equality because the two backends intentionally
    # produce different output shapes)
    assert auto_out != regex_out or not regex_out
    # Both should be non-empty on this test input
    assert auto_out
