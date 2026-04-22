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
from skimr.extract import metadata  # noqa: E402
from skimr.extract._backends import resolve  # noqa: E402


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
