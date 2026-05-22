from lede._types import SummaryResult


def test_summary_result_has_pinned_headings_default_empty():
    r = SummaryResult(summary="hi")
    assert r.pinned_headings == ()
    assert str(r) == "hi"
