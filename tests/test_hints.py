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
