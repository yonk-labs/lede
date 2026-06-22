"""Regression (#12): money amounts retain their magnitude word.

Previously "$5 million" truncated to "$5" (worse than no value). The money
regex in both `extract.stats` and `extract.metadata` now captures a trailing
magnitude word.
"""
from lede.extract import metadata, stats


def test_stats_captures_magnitude():
    vals = [s.value for s in stats("We raised $5 million this year.")]
    assert "$5 million" in vals, vals


def test_stats_billion_dollars_value2_path():
    vals = [s.value for s in stats("Revenue hit 2.3 billion dollars.")]
    assert "2.3 billion" in vals, vals


def test_metadata_amounts_keep_magnitude():
    assert metadata("We raised $5 million.").amounts == ("$5 million",)


def test_plain_amount_unchanged():
    # No regression for amounts without a magnitude word.
    assert metadata("It cost $5.").amounts == ("$5",)


def test_not_greedy_into_millionaire():
    # Word boundary: "millionaire" must not be captured as the magnitude.
    assert metadata("The $5 millionaire arrived.").amounts == ("$5",)
