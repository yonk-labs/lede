"""extract.stats tests."""
from skimr.extract import stats


def test_stats_finds_money():
    r = stats("Our Q2 budget was $120K and we spent $45,000 on licenses.")
    values = {s.value for s in r}
    assert "$120K" in values or "$120" in values
    assert any("45,000" in s.value or "45000" in s.value for s in r)
    for s in r:
        if "120" in s.value or "45" in s.value:
            assert s.stat_type == "money"
            assert s.unit == "usd"


def test_stats_finds_percent():
    r = stats("Revenue grew by 23 percent last quarter and margins improved 8%.")
    pcts = [s for s in r if s.stat_type == "percent"]
    assert len(pcts) >= 2
    assert any("23" in s.value for s in pcts)
    assert any("8" in s.value for s in pcts)


def test_stats_finds_dates():
    r = stats("Contract signed on 2025-06-14, effective 2026-01-01.")
    dates = [s for s in r if s.stat_type == "date"]
    assert any("2025-06-14" in s.value for s in dates)
    assert any("2026-01-01" in s.value for s in dates)


def test_stats_finds_durations():
    r = stats("Migration will take 3 months. Warranty covers 5 years.")
    durs = [s for s in r if s.stat_type == "duration"]
    assert any("3 months" in s.value.lower() or "months" in s.unit for s in durs)
    assert any("5 years" in s.value.lower() or "years" in s.unit for s in durs)


def test_stats_attaches_context_sentence():
    r = stats("Hello world. Revenue grew 23 percent year over year. Other sentence.")
    pct = [s for s in r if s.stat_type == "percent"]
    assert pct
    assert "Revenue grew 23 percent" in pct[0].context_sentence


def test_stats_empty_on_no_numbers():
    assert stats("No numbers here.") == ()
    assert stats("") == ()


def test_stats_extracts_bare_year_as_date():
    """T13a: bare 4-digit years in 1900-2099 emit as stat_type='date'."""
    text = "Proposed by Bentley in 1975. Refined by Malkov in 2016."
    facts = stats(text)
    years = [f.value for f in facts if f.stat_type == "date"]
    assert "1975" in years
    assert "2016" in years


def test_stats_extracts_hyphenated_duration():
    """T13a: hyphenated number-unit forms like '90-day' match."""
    text = "We keep a 90-day retention window. The 14-day trial ends soon."
    durations = {(f.value, f.unit) for f in stats(text) if f.stat_type == "duration"}
    assert ("90 day", "day") in durations
    assert ("14 day", "day") in durations


def test_stats_extracts_basis_points_and_terabytes():
    """T13a: added count keywords 'basis points' and 'terabytes'."""
    text = "Yields climbed 8 basis points. Volume reached 2 terabytes per day."
    counts = {(f.value, f.unit) for f in stats(text) if f.stat_type == "count"}
    assert ("8", "basis points") in counts
    assert ("2", "terabytes") in counts
