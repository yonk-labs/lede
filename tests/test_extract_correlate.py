"""extract.correlate_facts tests."""
from skimr.extract import correlate_facts


def test_correlates_entity_with_multiple_numbers():
    text = (
        "Revenue grew 23 percent year over year. "
        "Revenue for the quarter was $4.2 billion in total. "
        "Revenue per customer rose by 8 percent."
    )
    r = correlate_facts(text)
    # "revenue" appears 3+ times with multiple numbers -> should pair
    entities = {pf.entity.lower() for pf in r}
    assert any("revenue" in e for e in entities)
    # Should carry polarity where cue words present
    growth_pfs = [pf for pf in r if pf.polarity == "growth"]
    assert growth_pfs


def test_ignores_entities_appearing_once():
    text = "The server returned a 500 error. The team had lunch at noon."
    r = correlate_facts(text)
    # No entity repeats with numeric facts -> empty
    assert r == ()


def test_decline_polarity_detected():
    text = (
        "Costs fell by 12 percent this quarter. "
        "Costs declined by $5 million overall. "
        "Costs decreased as staff reductions took effect."
    )
    r = correlate_facts(text)
    entities = {pf.entity.lower() for pf in r}
    assert any("cost" in e for e in entities)
    declines = [pf for pf in r if pf.polarity == "decline"]
    assert declines


def test_empty_input():
    assert correlate_facts("") == ()
