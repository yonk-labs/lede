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


class TestSynonymExpansion:
    def test_synonyms_for_car(self):
        # Skip if nltk isn't installed in the current env.
        pytest.importorskip("nltk")
        out = expand_hints(["car"], kinds=("synonyms",), top_k=5)
        # Original is preserved.
        assert "car" in out
        # WordNet has stable synonyms for "car" (auto, automobile, etc.).
        assert len(out) > 1

    def test_synonyms_dict_scales_weights(self):
        pytest.importorskip("nltk")
        out = expand_hints({"car": 2.0}, kinds=("synonyms",), top_k=5)
        assert isinstance(out, dict)
        assert out["car"] == 2.0
        # Expansion terms get weight 0.5 * 2.0 = 1.0
        for k, v in out.items():
            if k != "car":
                assert v == 1.0

    def test_multi_word_synonyms_passthrough(self):
        pytest.importorskip("nltk")
        # WordNet has no entry for "John Smith"; the multi-token hint
        # passes through unchanged.
        out = expand_hints(["John Smith"], kinds=("synonyms",))
        assert out == ["John Smith"]

    def test_synonyms_combined_with_lemma(self):
        pytest.importorskip("nltk")
        # "cars" lemmatizes to "car"; WordNet has synonyms for "car".
        out = expand_hints(["cars"], kinds=("lemma", "synonyms"), top_k=3)
        # Original is present.
        assert "cars" in out
        # Lemma "car" is present.
        assert "car" in out
        # At least one synonym expansion came in.
        assert len(out) > 2

    def test_synonyms_missing_nltk_raises(self, monkeypatch):
        # Force nltk to be unimportable in the function's namespace.
        import sys
        monkeypatch.setitem(sys.modules, "nltk", None)
        with pytest.raises(ImportError, match="lede-spacy\\[synonyms\\]"):
            expand_hints(["car"], kinds=("synonyms",))


class TestSimilarExpansion:
    def _has_vector_model(self):
        # similar now loads a vector model (en_core_web_md by default), not sm.
        from lede_spacy._ner import _nlp
        try:
            nlp = _nlp("en_core_web_md")
        except ImportError:
            return False
        return nlp.vocab.vectors_length > 0

    def test_similar_missing_vector_model_errors(self):
        # When the vector model isn't installed, similar raises an actionable
        # error naming the model + download command.
        if self._has_vector_model():
            pytest.skip("vector model installed; cannot test the missing-model error")
        with pytest.raises((ImportError, RuntimeError), match="en_core_web_md"):
            expand_hints(["county"], kinds=("similar",))

    def test_similar_with_vectors(self):
        if not self._has_vector_model():
            pytest.skip("no vector model (need en_core_web_md or _lg)")
        out = expand_hints(["county"], kinds=("similar",), top_k=3)
        assert "county" in out
        assert len(out) > 1

    def test_similar_multi_word_passthrough(self):
        if not self._has_vector_model():
            pytest.skip("no vector model (need en_core_web_md or _lg)")
        out = expand_hints(["John Smith"], kinds=("similar",))
        # Multi-word hints pass through unchanged for similar.
        assert out == ["John Smith"]
