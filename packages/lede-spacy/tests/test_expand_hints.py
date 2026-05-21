"""Tests for lede_spacy.expand_hints()."""
import pytest

from lede_spacy import expand_hints


class TestLemmaExpansion:
    def test_list_input_returns_list(self):
        out = expand_hints(["counties"], kinds=("lemma",))
        assert isinstance(out, list)
        assert "counties" in out
        assert "county" in out

    def test_dict_input_returns_dict_with_scaled_weights(self):
        out = expand_hints({"counties": 2.0}, kinds=("lemma",))
        assert isinstance(out, dict)
        assert out["counties"] == 2.0
        # Lemma "county" should have weight 0.5 * 2.0 = 1.0
        assert out.get("county") == 1.0

    def test_running_lemmatizes_to_run(self):
        out = expand_hints(["running"], kinds=("lemma",))
        assert "run" in out

    def test_multi_word_phrase_rejoined(self):
        # "John Smith" stays as the phrase; lemma pass is no-op for proper nouns.
        out = expand_hints(["John Smith"], kinds=("lemma",))
        assert "John Smith" in out

    def test_unchanged_input_dedups_to_single_entry(self):
        # "county" lemmatizes to "county"; output deduplicates.
        out = expand_hints(["county"], kinds=("lemma",))
        assert out == ["county"]

    def test_empty_list_input(self):
        assert expand_hints([], kinds=("lemma",)) == []

    def test_empty_dict_input(self):
        assert expand_hints({}, kinds=("lemma",)) == {}

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="unknown kind"):
            expand_hints(["foo"], kinds=("unknown",))

    def test_composition_with_summarize(self):
        from lede import summarize
        text = (
            "Several counties met. Cook County is in Illinois. "
            "The counties voted unanimously. Other states followed."
        )
        hints = expand_hints(["counties"], kinds=("lemma",))
        result = summarize(text, max_length=120, hints=hints).summary
        # Either "county" or "counties" should drive selection.
        low = result.lower()
        assert "county" in low or "counties" in low
