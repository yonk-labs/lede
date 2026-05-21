"""Tests for hint-biased extraction (v0.4)."""
import pytest

from lede._hints import (
    preprocess_hints,
    match_count,
)


class TestPreprocessHints:
    def test_list_input_lowercases_and_strips(self):
        assert preprocess_hints(["  County  ", "John SMITH"]) == [
            ("county", 1.0),
            ("john smith", 1.0),
        ]

    def test_collapses_internal_whitespace(self):
        assert preprocess_hints(["John   Smith"]) == [("john smith", 1.0)]

    def test_dict_input_preserves_weights(self):
        out = preprocess_hints({"County": 2.0, "John Smith": 0.5})
        assert sorted(out) == sorted([("county", 2.0), ("john smith", 0.5)])

    def test_drops_empty_and_whitespace_only(self):
        assert preprocess_hints(["", "  ", "county"]) == [("county", 1.0)]

    def test_empty_list_returns_empty(self):
        assert preprocess_hints([]) == []

    def test_none_returns_empty(self):
        assert preprocess_hints(None) == []


class TestMatchCount:
    def test_single_token_case_insensitive(self):
        assert match_count("smith", "John Smith lives there") == 1

    def test_token_boundary_blocks_prefix(self):
        assert match_count("smith", "blacksmith works late") == 0

    def test_token_boundary_blocks_suffix(self):
        assert match_count("smith", "the smiths arrived") == 0

    def test_phrase_match_contiguous(self):
        assert match_count("john smith", "John Smith Sr. is here") == 1

    def test_phrase_match_rejects_middle_initial(self):
        assert match_count("john smith", "John P. Smith arrived") == 0

    def test_multiple_non_overlapping_matches(self):
        assert match_count("smith", "Smith spoke. Then Smith left.") == 2

    def test_apostrophe_word_boundary(self):
        assert match_count("o'brien", "O'Brien arrived early") == 1

    def test_hyphenated_phrase(self):
        assert match_count("state-of-the-art", "state-of-the-art design here") == 1


class TestRoundToInt:
    def test_zero_focus(self):
        from lede._hints import round_to_int
        assert round_to_int(500, 0.0) == 0

    def test_full_focus(self):
        from lede._hints import round_to_int
        assert round_to_int(500, 1.0) == 500

    def test_half_focus_even_budget(self):
        from lede._hints import round_to_int
        assert round_to_int(500, 0.5) == 250

    def test_half_focus_odd_budget(self):
        from lede._hints import round_to_int
        # 501 * 0.5 = 250.5 → rounds to 251 in both runtimes
        assert round_to_int(501, 0.5) == 251

    def test_default_focus(self):
        from lede._hints import round_to_int
        # 500 * 0.7 = 350
        assert round_to_int(500, 0.7) == 350

    def test_count_budget(self):
        from lede._hints import round_to_int
        # 10 facts * 0.7 = 7
        assert round_to_int(10, 0.7) == 7


class TestHintBonus:
    def test_no_hints_returns_zero(self):
        from lede._hints import hint_bonus
        assert hint_bonus("John Smith lives there", []) == 0.0

    def test_single_match(self):
        from lede._hints import hint_bonus
        # 1 match * weight 1.0 * BASE 0.5 = 0.5
        assert hint_bonus("John Smith lives", [("smith", 1.0)]) == 0.5

    def test_multiple_matches_below_cap(self):
        from lede._hints import hint_bonus
        # 2 matches * 1.0 * 0.5 = 1.0
        assert hint_bonus("Smith. Smith left.", [("smith", 1.0)]) == 1.0

    def test_match_cap_saturates_at_three(self):
        from lede._hints import hint_bonus
        # 5 occurrences capped at 3: 3 * 1.0 * 0.5 = 1.5
        s = "Smith Smith Smith Smith Smith"
        assert hint_bonus(s, [("smith", 1.0)]) == 1.5

    def test_per_hint_weight_multiplies(self):
        from lede._hints import hint_bonus
        # 1 match * weight 2.0 * 0.5 = 1.0
        assert hint_bonus("Smith here", [("smith", 2.0)]) == 1.0

    def test_multiple_hints_sum(self):
        from lede._hints import hint_bonus
        # smith: 1 match * 1.0 * 0.5 = 0.5
        # county: 1 match * 1.0 * 0.5 = 0.5
        # total = 1.0
        s = "Smith lives in Cook County"
        assert hint_bonus(s, [("smith", 1.0), ("county", 1.0)]) == 1.0


class TestSelectByChars:
    def test_simple_budget(self):
        from lede._hints import select_by_chars
        # Sentences: index 0 score 1.0 (10 chars), index 1 score 2.0 (20 chars)
        scores = [1.0, 2.0]
        lengths = [10, 20]
        # Budget 25 — both fit (20 + 10 = 30 > 25; pick higher-score 20 first, then 10? No: 20+10=30 doesn't fit)
        # 20 first (score 2.0), then check 10 (score 1.0): used=20, separator=1, 20+1+10=31 > 25. Skip.
        assert select_by_chars(scores, lengths, budget=25, exclude=set()) == {1}

    def test_separator_accounted(self):
        from lede._hints import select_by_chars
        scores = [1.0, 0.9, 0.8]
        lengths = [10, 10, 10]
        # budget 22: first pick 10 (used=10), second 10+1=11 fits (used=21), third needs 10+1=11 → 32>22
        assert select_by_chars(scores, lengths, budget=22, exclude=set()) == {0, 1}

    def test_excludes_skipped(self):
        from lede._hints import select_by_chars
        scores = [2.0, 1.0]
        lengths = [10, 10]
        assert select_by_chars(scores, lengths, budget=20, exclude={0}) == {1}

    def test_zero_budget_returns_empty(self):
        from lede._hints import select_by_chars
        assert select_by_chars([1.0], [10], budget=0, exclude=set()) == set()

    def test_negative_infinity_score_skipped(self):
        from lede._hints import select_by_chars
        scores = [float("-inf"), 1.0]
        lengths = [10, 10]
        assert select_by_chars(scores, lengths, budget=50, exclude=set()) == {1}


class TestSelectByCount:
    def test_simple_topn(self):
        from lede._hints import select_by_count
        scores = [0.5, 1.0, 0.3, 0.9]
        assert select_by_count(scores, count=2, exclude=set()) == {1, 3}

    def test_excludes_skipped(self):
        from lede._hints import select_by_count
        scores = [2.0, 1.0, 0.5]
        assert select_by_count(scores, count=2, exclude={0}) == {1, 2}

    def test_zero_count(self):
        from lede._hints import select_by_count
        assert select_by_count([1.0, 2.0], count=0, exclude=set()) == set()

    def test_negative_infinity_score_skipped(self):
        from lede._hints import select_by_count
        scores = [float("-inf"), 1.0]
        assert select_by_count(scores, count=2, exclude=set()) == {1}

    def test_position_tiebreak(self):
        from lede._hints import select_by_count
        # ties broken by lower index first
        assert select_by_count([1.0, 1.0, 1.0], count=2, exclude=set()) == {0, 1}


from lede import summarize


SAMPLE = (
    "The town council met on Tuesday. "
    "John Smith presented his case to the assembly. "
    "Smith argued for lower property taxes. "
    "The council voted to defer the decision. "
    "Cook County is the second-most populous county in Illinois. "
    "Local farmers expressed concern about water rights. "
    "The next meeting is scheduled for the third of next month. "
    "John Smith lives in Cook County and runs a small business."
)


class TestSummarizeHints:
    def test_backward_compat_no_hints(self):
        # Same call as v0.3.0 — must produce identical output to the no-hint path.
        a = summarize(SAMPLE, max_length=300).summary
        b = summarize(SAMPLE, max_length=300, hints=None).summary
        assert a == b

    def test_hint_focus_zero_equals_no_hints(self):
        a = summarize(SAMPLE, max_length=300).summary
        b = summarize(SAMPLE, max_length=300, hints=["county"], hint_focus=0.0).summary
        assert a == b

    def test_soft_hints_lean_toward_matches(self):
        # The hint sentence ("John Smith lives in Cook County...") should appear.
        result = summarize(SAMPLE, max_length=200, hints=["john smith", "county"]).summary
        assert "John Smith lives in Cook County" in result

    def test_hard_full_focus_only_matching(self):
        # hint_mode='hard' + hint_focus=1.0 — every selected sentence contains a hint.
        result = summarize(
            SAMPLE,
            max_length=200,
            hints=["smith"],
            hint_focus=1.0,
            hint_mode="hard",
        ).summary
        # Every retained sentence (split on '. ') should contain "Smith".
        for sent in result.split(". "):
            stripped = sent.strip(". ")
            if stripped:
                assert "smith" in stripped.lower()

    def test_hard_mode_zero_matches_falls_back(self):
        # Hint that matches nothing in HARD mode + focus=1.0 → falls back to truncation.
        result = summarize(
            SAMPLE,
            max_length=200,
            hints=["xyzzy"],
            hint_focus=1.0,
            hint_mode="hard",
        ).summary
        assert result  # not empty; truncation fallback

    def test_legacy_mode_rejects_hints(self):
        with pytest.raises(ValueError, match="hints not supported in legacy mode"):
            summarize(SAMPLE, max_length=200, mode="legacy", hints=["smith"])

    def test_hint_focus_out_of_range(self):
        with pytest.raises(ValueError, match="hint_focus"):
            summarize(SAMPLE, max_length=200, hints=["smith"], hint_focus=1.5)
        with pytest.raises(ValueError, match="hint_focus"):
            summarize(SAMPLE, max_length=200, hints=["smith"], hint_focus=-0.1)

    def test_hint_mode_invalid(self):
        with pytest.raises(ValueError, match="hint_mode"):
            summarize(SAMPLE, max_length=200, hints=["smith"], hint_mode="medium")

    def test_unknown_mode_raises_even_with_hints(self):
        with pytest.raises(ValueError, match="unknown mode"):
            summarize(SAMPLE, max_length=200, mode="foobar", hints=["smith"])

    def test_empty_hints_list_equals_none(self):
        a = summarize(SAMPLE, max_length=300).summary
        b = summarize(SAMPLE, max_length=300, hints=[]).summary
        assert a == b

    def test_dict_hints_apply_weights(self):
        # Dict input with positive weights — must not raise; result should still mention hint.
        result = summarize(
            SAMPLE,
            max_length=200,
            hints={"john smith": 2.0, "county": 1.0},
        ).summary
        assert "John Smith" in result or "Cook County" in result


class TestCoverageHints:
    def test_coverage_accepts_hints(self):
        result = summarize(
            SAMPLE,
            max_length=200,
            mode="coverage",
            hints=["county"],
        ).summary
        assert result  # non-empty


from lede.extract import key_facts


class TestKeyFactsHints:
    def test_backward_compat_no_hints(self):
        a = key_facts(SAMPLE, max_facts=5)
        b = key_facts(SAMPLE, max_facts=5, hints=None)
        assert a == b

    def test_hard_full_focus_only_matching(self):
        facts = key_facts(
            SAMPLE,
            max_facts=10,
            hints=["smith"],
            hint_focus=1.0,
            hint_mode="hard",
        )
        for f in facts:
            assert "smith" in f.lower()

    def test_hint_quota_split(self):
        # max_facts=10, hint_focus=0.5 → up to 5 hint-bearing + 5 any
        facts = key_facts(
            SAMPLE,
            max_facts=10,
            hints=["county"],
            hint_focus=0.5,
            hint_mode="hard",
        )
        # If any county-bearing candidate exists in SAMPLE, at least one returned.
        hint_bearing = [f for f in facts if "county" in f.lower()]
        assert len(hint_bearing) >= 1 or len(facts) == 0

    def test_hint_focus_out_of_range(self):
        with pytest.raises(ValueError, match="hint_focus"):
            key_facts(SAMPLE, max_facts=5, hints=["county"], hint_focus=2.0)

    def test_hard_mode_does_not_leak_non_matching_facts(self):
        # Stat-bearing sentences that don't all contain the hint — confirms
        # the hard-mode rollover stays restricted to hint-matching candidates.
        text = (
            "The company earned $5 million in Q3 2023, down from $7 million the prior year. "
            "Smith filed the annual report on March 15, 2024. "
            "Total employees grew by 12 percent to reach 450 staff. "
            "Revenue fell 8 percent year-over-year to $4.2 billion."
        )
        facts = key_facts(
            text,
            max_facts=10,
            hints=["smith"],
            hint_focus=1.0,
            hint_mode="hard",
        )
        # In hard mode + focus=1.0, every returned fact MUST contain "smith".
        # The non-Smith stat-bearing sentences must not leak in via rollover.
        for f in facts:
            assert "smith" in f.lower(), f"LEAK: {f!r}"
        # Sanity: the Smith-bearing fact should be present.
        assert any("smith" in f.lower() for f in facts), \
            "expected at least one Smith-bearing fact"
