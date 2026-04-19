from pathlib import Path
from skimr.clean import strip_think

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "strip_think"


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
