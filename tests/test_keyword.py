from pathlib import Path
from lede.keyword import extract_keyword


def test_extract_keyword_picks_sentences_with_matches():
    text = (
        "The demo went well. "
        "Main concern is pricing and budget. "
        "Will follow up next Tuesday."
    )
    result = extract_keyword(text, "pricing budget", num_sentences=1)
    assert "pricing" in result.lower()


def test_extract_keyword_respects_num_sentences():
    text = (
        "Main concern is pricing. "
        "Budget is tight. "
        "Cost is above plan. "
        "Will follow up next week."
    )
    result = extract_keyword(text, "pricing budget cost", num_sentences=2)
    # Returns 2 newline-separated sentences
    assert result.count("\n") == 1


def test_extract_keyword_causal_bonus():
    # "because" triggers +1.0 causal bonus; should rank above a neutral sentence.
    text = (
        "Revenue grew last quarter. "
        "The deal was lost because of pricing concerns. "
        "Meeting was scheduled."
    )
    result = extract_keyword(text, "pricing", num_sentences=1)
    assert "because" in result.lower()


def test_extract_keyword_empty_input_returns_empty():
    assert extract_keyword("", "pricing", num_sentences=3) == ""


def test_extract_keyword_empty_keywords_returns_empty():
    text = "A short sentence. Another one."
    # All tokens filtered (<3 chars) → empty string. Diverges from the SQL
    # reference's LEFT(text, 2000) silent chop, which was a footgun.
    assert extract_keyword(text, "x y", num_sentences=3) == ""
    assert extract_keyword(text, "", num_sentences=3) == ""
    assert extract_keyword(text, "   ", num_sentences=3) == ""


def test_extract_keyword_fixture_pricing_notes():
    fx = Path(__file__).resolve().parent.parent / "fixtures" / "keyword" / "pricing-notes"
    inp = (fx / "input.txt").read_text()
    expected_path = fx / "expected.txt"
    # If expected.txt was generated and committed, assert exact match.
    if expected_path.exists():
        import json
        cfg = json.loads((fx / "config.json").read_text())
        params = cfg.get("params", {})
        result = extract_keyword(
            inp,
            params["keywords"],
            num_sentences=params.get("num_sentences", 10),
        )
        assert result == expected_path.read_text()
