from lede._types import SummaryResult
from lede._pins import (
    nearest_heading_map,
    document_title_index,
    render_toc,
)


def test_summary_result_has_pinned_headings_default_empty():
    r = SummaryResult(summary="hi")
    assert r.pinned_headings == ()
    assert str(r) == "hi"


def test_nearest_heading_map_points_to_enclosing_heading():
    sentences = ["# Title", "Body one.", "## Sub", "Body two."]
    assert nearest_heading_map(sentences) == [None, 0, None, 2]


def test_document_title_index_depth1_at_start():
    assert document_title_index(["# Title", "Body."]) == 0


def test_document_title_index_none_when_body_precedes():
    assert document_title_index(["Body first.", "# Title"]) is None


def test_document_title_index_none_when_first_heading_not_depth1():
    assert document_title_index(["## Sub", "Body."]) is None


def test_render_toc_indents_by_depth():
    text = "# Top\n\nBody about the top matter here.\n\n## Sub\n\nMore body content follows here.\n"
    toc = render_toc(text)
    assert "Top" in toc
    assert "  Sub" in toc  # depth 2 => 2-space indent


from lede._pins import render_with_pins


def _sentences():
    return [
        "# Quarterly Report",
        "Revenue rose sharply this quarter overall.",
        "## Revenue",
        "Revenue grew twelve percent year over year.",
        "Costs were flat across the period.",
        "## Risks",
        "Supply chain risk remains elevated this year.",
    ]


def test_keep_headings_interleaves_and_pins_title():
    s = _sentences()
    selected = [1, 3, 6]
    body, pinned = render_with_pins(
        s, selected, keep_headings=True, include_toc=False, pin=None, text="\n".join(s)
    )
    assert pinned == ("# Quarterly Report", "## Revenue", "## Risks")
    assert body == (
        "# Quarterly Report\n"
        "Revenue rose sharply this quarter overall.\n"
        "## Revenue\n"
        "Revenue grew twelve percent year over year.\n"
        "## Risks\n"
        "Supply chain risk remains elevated this year."
    )


def test_keep_headings_false_joins_with_space():
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1, 3], keep_headings=False, include_toc=False, pin=None, text="\n".join(s)
    )
    assert pinned == ()
    assert body == "Revenue rose sharply this quarter overall. Revenue grew twelve percent year over year."


def test_pin_prepends_block_before_body():
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1], keep_headings=False, include_toc=False,
        pin=["Figure 3: Q3 revenue by region"], text="\n".join(s),
    )
    assert pinned == ()
    assert body == (
        "Figure 3: Q3 revenue by region\n\n"
        "Revenue rose sharply this quarter overall."
    )


def test_ordering_pin_then_toc_then_body():
    s = _sentences()
    body, _ = render_with_pins(
        s, [1], keep_headings=False, include_toc=True,
        pin=["PINNED LINE"], text="\n".join(s),
    )
    assert body.startswith("PINNED LINE\n\n")
    assert "Quarterly Report" in body.split("\n\n")[1]
    assert body.split("\n\n")[-1] == "Revenue rose sharply this quarter overall."


def test_title_not_double_emitted_when_also_enclosing_heading():
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1], keep_headings=True, include_toc=False, pin=None, text="\n".join(s)
    )
    assert pinned == ("# Quarterly Report",)
    assert body.count("# Quarterly Report") == 1
