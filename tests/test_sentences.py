import pytest

from skimr.sentences import split_sentences


def test_simple_periods():
    text = "Revenue grew. Costs fell. Margins improved."
    assert split_sentences(text) == [
        "Revenue grew.",
        "Costs fell.",
        "Margins improved.",
    ]


def test_question_and_exclamation():
    text = "Did it work? Yes! It did."
    assert split_sentences(text) == ["Did it work?", "Yes!", "It did."]


def test_abbreviation_not_split():
    text = "Dr. Smith analyzed the Q4 results. Revenue grew 23%."
    assert split_sentences(text) == [
        "Dr. Smith analyzed the Q4 results.",
        "Revenue grew 23%.",
    ]


def test_us_uk_abbreviations_not_split():
    text = "The U.S. market grew. The U.K. followed."
    assert split_sentences(text) == [
        "The U.S. market grew.",
        "The U.K. followed.",
    ]


def test_decimal_not_split():
    text = "Pi is 3.14 approximately. E is 2.71."
    assert split_sentences(text) == [
        "Pi is 3.14 approximately.",
        "E is 2.71.",
    ]


def test_paragraph_break_splits():
    text = "First sentence.\n\nSecond paragraph."
    assert split_sentences(text) == ["First sentence.", "Second paragraph."]


def test_empty_input_returns_empty_list():
    assert split_sentences("") == []


def test_single_sentence_no_terminator():
    # SUMMARIZATION.md doesn't require a final period
    assert split_sentences("Just one fragment") == ["Just one fragment"]


def test_nul_in_input_raises():
    with pytest.raises(ValueError, match="reserved sentinel"):
        split_sentences("hello\x00world. Next.")
