from pathlib import Path
from skimr.clean import clean_text, strip_think

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "strip_think"
CLEAN_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "clean_text"


def test_simple_block():
    assert strip_think("<think>thinking</think>\nRevenue grew.") == "Revenue grew."


def test_no_block_returns_unchanged_trimmed():
    text = "Revenue grew 23% in Q4. No think block present."
    assert strip_think(text) == text


def test_multiple_blocks():
    text = "<think>a</think>\nOne.\n<think>b</think>\nTwo."
    assert strip_think(text) == "One.\nTwo."


def test_multiline_block():
    text = "<think>\nline one\nline two\n</think>\nAfter."
    assert strip_think(text) == "After."


def test_fixture_simple_block():
    input_text = (FIXTURES / "simple-block" / "input.txt").read_text()
    expected = (FIXTURES / "simple-block" / "expected.txt").read_text()
    assert strip_think(input_text) == expected


def test_fixture_no_think_block():
    input_text = (FIXTURES / "no-think-block" / "input.txt").read_text()
    expected = (FIXTURES / "no-think-block" / "expected.txt").read_text()
    assert strip_think(input_text) == expected


def test_fixture_multiple_blocks():
    input_text = (FIXTURES / "multiple-blocks" / "input.txt").read_text()
    expected = (FIXTURES / "multiple-blocks" / "expected.txt").read_text()
    assert strip_think(input_text) == expected


def test_clean_text_removes_bold_markdown():
    input_text = (CLEAN_FIXTURES / "markdown-basic" / "input.txt").read_text()
    expected = (CLEAN_FIXTURES / "markdown-basic" / "expected.txt").read_text()
    assert clean_text(input_text) == expected


def test_clean_text_strips_filler_phrases():
    text = "Just wanted to follow up on pricing."
    result = clean_text(text)
    assert "just wanted to" not in result.lower()
    assert "pricing" in result


def test_clean_text_strips_filler_words():
    text = "Basically, the customer is actually concerned."
    result = clean_text(text)
    assert "basically" not in result
    assert "actually" not in result
    assert "customer" in result


def test_clean_text_strips_crm_boilerplate():
    text = "Pricing is an issue.\nNo updates.\nCalendar invite sent."
    result = clean_text(text)
    assert "no updates" not in result
    assert "calendar invite sent" not in result
    assert "pricing is an issue" in result


def test_clean_text_lowercases():
    assert clean_text("HELLO WORLD") == "hello world"


def test_clean_text_collapses_blank_lines():
    text = "line one\n\n\nline two"
    result = clean_text(text)
    assert result == "line one\nline two"


def test_clean_text_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""
