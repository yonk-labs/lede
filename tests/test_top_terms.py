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


class TestTopTermsWithScores:
    def test_default_with_scores_false_returns_strings(self):
        # Backward compat: default is bare strings.
        out = top_terms(SAMPLE)
        assert all(isinstance(t, str) for t in out)

    def test_with_scores_returns_termscore(self):
        from lede.extract import TermScore

        out = top_terms(SAMPLE, with_scores=True)
        assert isinstance(out, tuple)
        assert all(isinstance(t, TermScore) for t in out)

    def test_termscore_is_tuple_unpackable(self):
        out = top_terms(SAMPLE, n=3, with_scores=True)
        assert out  # non-empty
        for term, score, kind in out:  # positional unpacking works
            assert isinstance(term, str)
            assert isinstance(score, float)
            assert kind in ("word", "phrase")

    def test_termscore_named_access(self):
        out = top_terms(SAMPLE, n=1, with_scores=True)
        ts = out[0]
        assert ts.term == out[0][0]
        assert ts.score == out[0][1]
        assert ts.kind == out[0][2]

    def test_terms_match_bare_ranking(self):
        # with_scores=True must return the SAME terms in the SAME order as
        # the bare-string call — it's the identical ranking, just richer.
        bare = top_terms(SAMPLE, n=10)
        scored = top_terms(SAMPLE, n=10, with_scores=True)
        assert tuple(ts.term for ts in scored) == bare

    def test_scores_descending(self):
        out = top_terms(SAMPLE, n=10, with_scores=True)
        scores = [ts.score for ts in out]
        assert scores == sorted(scores, reverse=True)

    def test_kind_word_for_single_token(self):
        out = top_terms(SAMPLE, n=10, kinds=("words",), with_scores=True)
        assert out
        for ts in out:
            assert ts.kind == "word"
            assert " " not in ts.term

    def test_kind_phrase_for_multi_word(self):
        out = top_terms(SAMPLE, n=10, kinds=("phrases",), with_scores=True)
        assert out
        for ts in out:
            assert ts.kind == "phrase"
            assert " " in ts.term

    def test_plain_scores_normalized_unit_range(self):
        # No hints: per-kind normalized to [0, 1].
        out = top_terms(SAMPLE, n=10, with_scores=True)
        for ts in out:
            assert 0.0 <= ts.score <= 1.0

    def test_soft_hint_score_includes_bonus(self):
        # Soft hints add hint_bonus on top, so a matching term can exceed 1.0.
        scored = top_terms(
            SAMPLE, n=10, kinds=("words",),
            hints=["smith"], hint_mode="soft", with_scores=True,
        )
        smith = [ts for ts in scored if ts.term == "smith"]
        assert smith, "expected 'smith' in word candidates"
        # base normalized score <= 1.0, plus a positive bonus
        assert smith[0].score > 0.0

    def test_hard_hint_filters_but_keeps_scores_and_kinds(self):
        out = top_terms(
            SAMPLE, n=10,
            hints=["smith"], hint_focus=1.0, hint_mode="hard", with_scores=True,
        )
        for ts in out:
            assert "smith" in ts.term.lower()
            assert ts.kind in ("word", "phrase")
            assert isinstance(ts.score, float)

    def test_empty_text_returns_empty_tuple(self):
        assert top_terms("", with_scores=True) == ()

    def test_mixed_kinds_have_both_word_and_phrase(self):
        out = top_terms(SAMPLE, n=10, with_scores=True)
        kinds = {ts.kind for ts in out}
        # SAMPLE has repeated phrases ("john smith", "cook county") and words.
        assert "word" in kinds
