"""extract.outline tests."""
from skimr.extract import outline, Section


def test_outline_captures_markdown_sections():
    text = (
        "# Introduction\n"
        "The team discussed the new pipeline. Sarah presented the charter.\n\n"
        "## Goals\n"
        "Decouple the ingest path. Shard writers for scale. Add backpressure.\n\n"
        "## Risks\n"
        "Data loss during cutover is the highest severity. "
        "Unexpected consumer behavior is second."
    )
    out = outline(text)
    names = [s.name for s in out]
    assert "Introduction" in names
    assert "Goals" in names
    assert "Risks" in names


def test_outline_representative_is_non_heading_sentence():
    text = (
        "## Results\n"
        "Revenue grew by 23 percent. Costs declined. Margins expanded."
    )
    out = outline(text)
    assert len(out) == 1
    assert out[0].name == "Results"
    # representative should contain actual content, not the heading itself
    assert "Revenue" in out[0].representative_sentence or \
           "Costs" in out[0].representative_sentence or \
           "Margins" in out[0].representative_sentence
    assert out[0].representative_sentence != "## Results"


def test_outline_depth_reflects_markdown_level():
    text = (
        "# Top\nBody sentence one is here.\n\n"
        "## Mid\nMid body sentence one is here.\n\n"
        "### Deep\nDeep body sentence one is here."
    )
    out = outline(text)
    depth_by_name = {s.name: s.depth for s in out}
    assert depth_by_name["Top"] == 1
    assert depth_by_name["Mid"] == 2
    assert depth_by_name["Deep"] == 3


def test_outline_returns_empty_for_no_headings():
    text = "Just some sentences. No headings here. Plain prose only."
    out = outline(text)
    assert out == ()


def test_outline_extracts_bare_title_case_headings():
    """T13b Class A: bare title-case single-line headings (Abstract, Results, etc.)."""
    text = (
        "Title: Test Paper\n\nAbstract\n\nWe investigate.\n\n"
        "Introduction\n\nDeterministic output matters.\n\n"
        "Conclusion\n\nFix is trivial.\n"
    )
    names = {s.name for s in outline(text)}
    assert "Abstract" in names
    assert "Introduction" in names
    assert "Conclusion" in names


def test_outline_extracts_numbered_sections():
    """T13b Class B: `\\d+. Section Name` with prefix stripped from name."""
    text = (
        "Privacy Policy\n\n"
        "1. Information We Collect\n\nWe collect data.\n\n"
        "2. How We Use Information\n\nWe process it.\n"
    )
    names = {s.name for s in outline(text)}
    assert "Information We Collect" in names
    assert "How We Use Information" in names


def test_outline_extracts_long_allcaps_title():
    """T13b Class C: ALLCAPS headings up to 80 chars."""
    text = (
        "SUPREME COURT OF THE UNITED STATES\n\n"
        "Opinion follows here with enough body to form a section.\n"
    )
    names = {s.name for s in outline(text)}
    assert "SUPREME COURT OF THE UNITED STATES" in names


def test_outline_still_excludes_short_body_sentences():
    """T13b regression: short body sentences like 'Costs declined.' must NOT match.

    Terminal period excludes them from _BARE_TITLE_RE; verify this invariant
    to prevent reintroducing the T6 FP class.
    """
    text = (
        "# Finance\n\n"
        "Costs declined. Revenue grew by 20 percent.\n"
    )
    names = {s.name for s in outline(text)}
    assert "Costs declined" not in names  # body sentence, not heading
    assert "Finance" in names              # markdown heading, legitimate
