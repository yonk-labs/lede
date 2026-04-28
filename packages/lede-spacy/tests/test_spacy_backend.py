"""Tests for the lede-spacy companion package."""
import pytest

# Guard: skip the entire module if spaCy or the model is unavailable at import.
spacy = pytest.importorskip("spacy")
try:
    spacy.load("en_core_web_sm")
except OSError:
    pytest.skip("en_core_web_sm not installed", allow_module_level=True)


# Importing lede_spacy must happen AFTER the skip guards so a clean
# skip message surfaces when the env lacks the model.
import lede_spacy  # noqa: E402  — import-for-side-effect: registers 'spacy' backend
from lede.extract import correlate_facts, metadata, phrases  # noqa: E402
from lede.extract._backends import resolve  # noqa: E402
from lede_spacy import spacy_phrases  # noqa: E402,F401


def test_lede_spacy_registers_on_import():
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
    # After lede_spacy is imported, auto prefers spacy
    assert m.entities  # non-empty — proves spacy ran, not regex


def test_warmup_is_callable():
    from lede_spacy import warmup
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
    # Since lede_spacy is imported at module top, auto should dispatch to spacy.
    # Use an input where the two backends produce different output: spaCy's
    # noun_chunks-based extractor requires a head noun (it won't emit
    # "learning models" without the determiner structure), while the regex
    # backend treats both as repeated n-grams.
    text = (
        "Machine learning models are powerful. "
        "Deep learning models work well. Models scale."
    )
    regex_out = phrases(text, backend="regex")
    spacy_out = phrases(text, backend="spacy")
    auto_out = phrases(text, backend="auto")
    # auto resolves to spacy in this test environment -> matches spacy, not regex
    assert auto_out == spacy_out
    assert auto_out != regex_out or not regex_out


# --- T11b: spacy_correlate_facts tests ---


def test_spacy_correlate_facts_registers_on_import():
    fn = resolve("spacy", "correlate_facts")
    assert callable(fn)


def test_correlate_facts_spacy_picks_up_entity_number_pairings():
    """T11b: spaCy backend finds entity-number pairings via NER + dependency."""
    text = (
        "Acme Cloud grew 14 percent in Q1. "
        "Acme Cloud saw revenues rise to $200 million. "
        "By contrast, Beta Inc fell 3 percent this quarter. "
        "Beta Inc lost another 5 percent in Q2."
    )
    pairings = correlate_facts(text, backend="spacy")
    entities = {p.entity for p in pairings}
    # Both entities should appear since each has 2 facts
    assert "acme cloud" in entities
    assert "beta inc" in entities


def test_correlate_facts_spacy_polarity_inference():
    """T11b: polarity comes from verb lemmas (grew -> growth, fell -> decline)."""
    text = (
        "Acme Cloud grew 10 percent. Acme Cloud grew 20 percent more. "
        "Beta Inc fell 5 percent. Beta Inc fell 8 percent further."
    )
    pairings = correlate_facts(text, backend="spacy")
    polarities_by_entity: dict[str, list[str]] = {}
    for p in pairings:
        polarities_by_entity.setdefault(p.entity, []).append(p.polarity)
    if "acme cloud" in polarities_by_entity:
        assert "growth" in polarities_by_entity["acme cloud"]
    if "beta inc" in polarities_by_entity:
        assert "decline" in polarities_by_entity["beta inc"]


def test_correlate_facts_spacy_filters_single_facts():
    """T11b: entities with only one numeric fact are excluded (>=2 rule)."""
    text = "Single Corp mentioned 10 percent. Other things happen."
    pairings = correlate_facts(text, backend="spacy")
    assert not any(p.entity == "single corp" for p in pairings)


def test_correlate_facts_spacy_empty_text():
    """T11b: empty input returns an empty tuple."""
    assert correlate_facts("", backend="spacy") == ()


def test_correlate_facts_spacy_deterministic():
    """T11b: same input produces identical output across calls (same model)."""
    text = (
        "Acme Cloud grew 14 percent in Q1. "
        "Acme Cloud saw revenues rise to $200 million. "
        "Beta Inc fell 3 percent this quarter. "
        "Beta Inc lost another 5 percent in Q2."
    )
    a = correlate_facts(text, backend="spacy")
    b = correlate_facts(text, backend="spacy")
    assert a == b
