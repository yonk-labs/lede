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
