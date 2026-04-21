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
