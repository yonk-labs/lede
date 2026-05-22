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
