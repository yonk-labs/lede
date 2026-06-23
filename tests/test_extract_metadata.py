"""extract.metadata core tests (stdlib path)."""
from lede.extract import metadata


def test_metadata_collects_iso_dates():
    m = metadata("Contract signed 2025-06-14; renewal 2026-01-01.")
    assert "2025-06-14" in m.dates
    assert "2026-01-01" in m.dates


def test_metadata_collects_money_amounts():
    m = metadata("Budget $120K; overage $45,000.")
    assert any("120K" in a or "120" in a for a in m.amounts)
    assert any("45,000" in a or "45000" in a for a in m.amounts)


def test_metadata_collects_urls():
    m = metadata(
        "See https://example.com/docs and http://example.org for details, "
        "plus contact privacy@example.org."
    )
    assert "https://example.com/docs" in m.urls
    assert "http://example.org" in m.urls


def test_metadata_no_entities_in_core():
    """Core path leaves entities empty; entities is reserved for lede-spacy companion."""
    m = metadata("Sarah Jones visited Johnson Education Co in Chicago.")
    # Core path never populates entities.
    assert m.entities == ()


def test_metadata_currency_prefix_amounts():
    """T13h: currency code before number (e.g. 'EUR 2.3 billion') captured as amount."""
    m = metadata("We raised EUR 2.3 billion and spent USD 5 million.")
    assert any("2.3 billion" in a or "2.3" in a for a in m.amounts), (
        f"EUR prefix not in amounts: {m.amounts}"
    )
    assert any("5 million" in a or "5" in a for a in m.amounts), (
        f"USD prefix not in amounts: {m.amounts}"
    )


def test_metadata_empty_on_empty_text():
    m = metadata("")
    assert m.dates == ()
    assert m.amounts == ()
    assert m.urls == ()
    assert m.entities == ()
