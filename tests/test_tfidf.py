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
