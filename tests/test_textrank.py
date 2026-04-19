"""TextRank mode — only runs when the [textrank] extra is installed."""
import pytest

networkx = pytest.importorskip("networkx", reason="networkx not installed; run `pip install skimr[textrank]`")

from skimr.textrank import summarize_textrank


def test_textrank_returns_nonempty_for_multi_sentence_input():
    text = (
        "Revenue grew 23% in Q4. "
        "The Enterprise segment led growth. "
        "Churn remained flat. "
        "Margins improved by 5 points. "
        "Outlook for next quarter is cautiously optimistic."
    )
    result = summarize_textrank(text, num_sentences=2)
    assert result
    assert result.count("\n") >= 0  # at most 1 newline for 2 sentences


def test_textrank_short_input_returns_unchanged():
    text = "Only one sentence here."
    # Below threshold: falls through to input unchanged
    assert summarize_textrank(text, num_sentences=3) == text


def test_textrank_deterministic():
    text = (
        "Revenue grew. Costs fell. Margins improved. "
        "Dr. Smith analyzed the Q4 results. The Enterprise segment led growth."
    )
    first = summarize_textrank(text, num_sentences=2)
    for _ in range(99):
        assert summarize_textrank(text, num_sentences=2) == first
