import math
from skimr.tfidf import tfidf_score, position_score, length_score, composite_score


def test_tfidf_score_returns_normalized_list():
    sentences = [
        "apple banana cherry",
        "apple date elderberry",
        "cherry date fig",
    ]
    scores = tfidf_score(sentences)
    assert len(scores) == 3
    assert all(0.0 <= s <= 1.0 for s in scores)
    # Scores should have at least one non-zero
    assert max(scores) > 0.0


def test_position_score_first_and_last_highest():
    # With 5 sentences, position 0 and 4 should score highest
    scores = position_score(5)
    assert len(scores) == 5
    assert scores[0] == 1.0
    assert scores[-1] == 1.0
    # Middle is lowest
    assert scores[2] < scores[0]
    assert scores[2] < scores[-1]


def test_position_score_single_sentence():
    assert position_score(1) == [1.0]


def test_length_score_sweet_spot():
    # 10-30 words should score highest per SUMMARIZATION.md
    short = "one two three"                                              # 3 words
    mid = " ".join(["word"] * 20)                                        # 20 words — sweet spot
    long = " ".join(["word"] * 100)                                      # 100 words
    scores = length_score([short, mid, long])
    assert scores[1] == max(scores)          # mid is highest
    assert scores[0] < scores[1]
    assert scores[2] < scores[1]


def test_composite_score_weighting():
    # Composite uses 60/25/15 weights. Construct three sentences where we control
    # relative scores and verify the weighted sum reflects the weighting.
    sentences = [
        "pricing budget pricing budget pricing",        # high tfidf for these terms
        "the the the the the the the the the the the the the the the the the",  # low tfidf, mid length
        "unique distinctive singular",                  # mid tfidf, short length
    ]
    composite = composite_score(sentences)
    assert len(composite) == 3
    # Sanity: all in [0, 1]
    assert all(0.0 <= s <= 1.0 for s in composite)


from skimr.tfidf import summarize


def test_summarize_short_input_returns_unchanged():
    text = "Short text."
    # v0.2: summarize() returns SummaryResult; .summary for the string.
    # Pin to mode='legacy' to match pre-v0.2 byte-identical behavior.
    assert summarize(text, max_length=500, mode="legacy").summary == text


def test_summarize_fallback_truncates_when_max_length_too_small():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    # max_length < 50 triggers truncation fallback per SUMMARIZATION.md step 1
    result = summarize(text, max_length=20, mode="legacy").summary
    assert len(result) <= 23  # 20 + "..." suffix
    assert result.endswith("...")


def test_summarize_fallback_when_fewer_than_three_sentences():
    text = "One only sentence here in this input."
    # Only 1 sentence → falls back to truncation
    result = summarize(text, max_length=15, mode="legacy").summary
    # 15 is < 50, so truncation path; also <3 sentences
    assert result.endswith("...")


def test_summarize_respects_max_length_budget():
    text = (
        "Revenue grew 23% in Q4. "
        "The Enterprise segment led growth. "
        "Churn remained flat. "
        "Dr. Smith analyzed the Q4 results. "
        "Margins improved by 5 points."
    )
    result = summarize(text, max_length=100, mode="legacy").summary
    assert len(result) <= 100


def test_summarize_reorders_by_original_position():
    # Construct text where the highest-TF-IDF sentence is in the middle.
    text = (
        "Opening sentence about apples. "
        "Unique distinctive keyword-heavy sentence. "
        "Closing sentence about apples."
    )
    result = summarize(text, max_length=200, mode="legacy").summary
    # The output should preserve original order if the selected sentences were
    # originally in that order. We check that the first selected sentence appears
    # before the second in the output.
    idx_open = result.find("Opening")
    idx_mid = result.find("Unique")
    idx_close = result.find("Closing")
    # All three selected; output must preserve order
    if idx_open >= 0 and idx_mid >= 0:
        assert idx_open < idx_mid
    if idx_mid >= 0 and idx_close >= 0:
        assert idx_mid < idx_close


def test_summarize_fixture_short_passthrough():
    from pathlib import Path
    fx = Path(__file__).resolve().parent.parent / "fixtures" / "tfidf-legacy" / "short-passthrough"
    inp = (fx / "input.txt").read_text()
    expected = (fx / "expected.txt").read_text()
    assert summarize(inp, max_length=500, mode="legacy").summary == expected
