"""extract.stats tests."""
import pytest

from lede.extract import correlate_facts, stats


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


def test_stats_extracts_common_count_nouns():
    """T13g: _COUNT_RE matches 'N items', 'N documents', 'N lines' style counts."""
    text = "We reviewed 5 items and 12 documents. Report had 47 lines. 3 entries were dropped."
    facts = stats(text)
    counts = {(f.value, f.unit) for f in facts if f.stat_type == "count"}
    assert ("5", "items") in counts
    assert ("12", "documents") in counts
    assert ("47", "lines") in counts
    assert ("3", "entries") in counts


def test_stats_extracts_tons_per_year():
    """T13g2: 'N tons per year' (and month/day) match as counts."""
    text = (
        "The permit authorizes 18 tons per year. "
        "EPA reduced the limit to 11 tons per year. "
        "The site emits 5 tons per month during peaks. "
        "Daily average is 2 tons per day."
    )
    counts = {(f.value, f.unit) for f in stats(text) if f.stat_type == "count"}
    assert ("18", "tons per year") in counts
    assert ("11", "tons per year") in counts
    assert ("5",  "tons per month") in counts
    assert ("2",  "tons per day") in counts


def test_stats_common_count_nouns_word_form():
    """T13g + T13e: word-form + common count noun (e.g. 'three items added')."""
    pytest.importorskip("text_to_num")
    text = "Three items added this week. Five documents reviewed."
    facts = stats(text, convert_word_names=True)
    counts = {f.value for f in facts if f.stat_type == "count"}
    assert any("three" in v.lower() or "3" in v for v in counts)
    assert any("five" in v.lower() or "5" in v for v in counts)


# -------- T13e: optional word-form number support via text_to_num --------

def test_stats_extracts_word_form_durations():
    """T13e: convert_word_names enables 'eight days' style matches."""
    pytest.importorskip("text_to_num")
    text = "He stayed in staging for eight days. The project took two weeks."
    facts = stats(text, convert_word_names=True)
    durations = {(f.value, f.unit) for f in facts if f.stat_type == "duration"}
    # Value preserves original word-form; unit is the regex-matched keyword.
    assert ("eight days", "day") in durations
    assert ("two weeks", "week") in durations


def test_stats_extracts_word_form_counts():
    """T13e: word-form counts like 'five thousand users'."""
    pytest.importorskip("text_to_num")
    text = "We saw five thousand users and processed seven hundred requests."
    facts = stats(text, convert_word_names=True)
    values = {f.value for f in facts if f.stat_type == "count"}
    assert any("five thousand" in v for v in values)
    assert any("seven hundred" in v for v in values)


def test_stats_default_flag_off_unchanged():
    """T13e: convert_word_names=False (default) keeps digit-only behavior."""
    text = "He stayed eight days and two weeks."
    facts = stats(text)  # default False
    # No word-form emissions in digit-only mode.
    assert not any("eight" in f.value.lower() for f in facts)
    assert not any("two" in f.value.lower() for f in facts)


def test_stats_word_form_flag_without_dep_raises():
    """T13e: flag on without text_to_num installed raises helpful ImportError."""
    try:
        import text_to_num  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="wordforms"):
            stats("eight days", convert_word_names=True)
    else:
        pytest.skip("text_to_num is installed; no-dep path cannot be exercised")


def test_stats_word_form_preserves_original_spans():
    """T13e: emitted value and phrase use the ORIGINAL word-form text,
    not the digit substitution."""
    pytest.importorskip("text_to_num")
    text = "Retention was seven years after account closure."
    facts = stats(text, convert_word_names=True)
    durs = [f for f in facts if f.stat_type == "duration"]
    assert durs
    f = durs[0]
    assert f.value == "seven years"
    assert "seven years" in f.phrase
    assert "seven years" in f.context_sentence
    # Crucially the digit form '7' should NOT appear in the emitted value.
    assert "7" not in f.value


def test_correlate_facts_propagates_convert_word_names():
    """T13e: correlate_facts forwards the flag to its internal stats() call."""
    pytest.importorskip("text_to_num")
    text = (
        "Retention was seven years after account closure. "
        "New regime extended it to thirteen months. "
        "After compliance review it dropped to thirty days. "
        "Retention was adjusted again to sixty days."
    )
    # Without flag: no word-form stats → no pairings.
    assert correlate_facts(text) == ()
    # With flag: should produce at least one pairing.
    pairings = correlate_facts(text, convert_word_names=True)
    assert len(pairings) >= 1


def test_stats_long_digit_run_does_not_hang():
    import time
    inp = "9" * 50_000 + " tons"
    t0 = time.perf_counter()
    out = stats(inp)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 100, f"ReDoS regression: stats() took {elapsed_ms:.0f}ms"
    assert out == ()


def test_stats_long_run_threshold_keeps_real_inputs():
    out = stats("Counter shows 1234567890123456 events today.")
    assert any(s.stat_type == "count" and s.unit == "events" for s in out)
    out = stats("Counter shows 1234567890123456789 events today.")
    assert any(s.stat_type == "count" for s in out)


def test_stats_bounded_quantifier_matches_everyday_tokens():
    cases = [
        ("Revenue grew 23 percent.", "percent", "23"),
        ("Spend hit $1.5M last quarter.", "money", "$1.5M"),
        ("1,234,567 users active.", "count", "1,234,567"),
        ("Plan covers 90 days.", "duration", "90 days"),
    ]
    for text, stat_type, value in cases:
        out = stats(text)
        assert any(s.stat_type == stat_type and s.value == value for s in out), (
            f"Missing {stat_type}={value} in {out}"
        )
