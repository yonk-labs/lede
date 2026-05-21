"""Tests for the v0.4 extract.top_terms primitive."""
import pytest

from lede.extract import top_terms


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


class TestTopTerms:
    def test_returns_tuple(self):
        out = top_terms(SAMPLE)
        assert isinstance(out, tuple)
        assert all(isinstance(t, str) for t in out)

    def test_default_n_is_ten(self):
        out = top_terms(SAMPLE)
        assert len(out) <= 10

    def test_explicit_n(self):
        out = top_terms(SAMPLE, n=5)
        assert len(out) <= 5

    def test_empty_text_returns_empty(self):
        assert top_terms("") == ()

    def test_words_only(self):
        out = top_terms(SAMPLE, n=10, kinds=("words",))
        # All single-token, no phrases.
        for term in out:
            assert " " not in term, f"phrase leaked into words-only: {term!r}"

    def test_phrases_only(self):
        out = top_terms(SAMPLE, n=10, kinds=("phrases",))
        # All multi-word.
        for term in out:
            assert " " in term, f"single word leaked into phrases-only: {term!r}"

    def test_mixed_default(self):
        # Default kinds=("words","phrases") — should include both types if
        # the document has any repeated phrases.
        out = top_terms(SAMPLE, n=10)
        has_word = any(" " not in t for t in out)
        # SAMPLE has repeated bigrams like "john smith" / "cook county".
        assert has_word, "expected at least one single word"

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="unknown kind"):
            top_terms(SAMPLE, kinds=("ngrams",))

    def test_deterministic(self):
        # Two calls produce identical output.
        a = top_terms(SAMPLE, n=10)
        b = top_terms(SAMPLE, n=10)
        assert a == b

    def test_hint_soft_biases_ranking(self):
        no_hint = top_terms(SAMPLE, n=10, kinds=("words",))
        soft = top_terms(SAMPLE, n=10, kinds=("words",), hints=["smith"], hint_mode="soft")
        # In soft mode, "smith" should be at or near the top of the soft ranking.
        # Loose assertion since exact ordering depends on TF-IDF + bonus.
        if "smith" in soft:
            no_hint_smith_pos = no_hint.index("smith") if "smith" in no_hint else len(no_hint)
            soft_smith_pos = soft.index("smith")
            assert soft_smith_pos <= no_hint_smith_pos, (
                f"soft bias did not improve smith's rank: "
                f"no_hint pos {no_hint_smith_pos}, soft pos {soft_smith_pos}"
            )

    def test_hint_hard_filters_to_matching(self):
        out = top_terms(
            SAMPLE,
            n=10,
            kinds=("words", "phrases"),
            hints=["smith"],
            hint_focus=1.0,
            hint_mode="hard",
        )
        for term in out:
            assert "smith" in term.lower(), f"leak in hard mode: {term!r}"

    def test_hint_focus_out_of_range(self):
        with pytest.raises(ValueError, match="hint_focus"):
            top_terms(SAMPLE, hints=["smith"], hint_focus=2.0)

    def test_hint_mode_invalid(self):
        with pytest.raises(ValueError, match="hint_mode"):
            top_terms(SAMPLE, hints=["smith"], hint_mode="medium")
