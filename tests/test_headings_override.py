import pytest
from lede import summarize
from lede._pins import render_toc_from_list, render_with_pins


def test_render_toc_from_list_dedupes_preserves_order():
    assert render_toc_from_list(["A", "B", "A", "C"]) == "A\nB\nC"


def test_override_matched_but_unselected_heading_still_survives():
    # "Appendix" matches body line 2 but its section (sentence 3) is not
    # selected, so the interleave pass never reaches it. It must still appear
    # (spec §4.3 step 6: every supplied heading is guaranteed present).
    sentences = ["Section A", "body one here", "Appendix", "appendix detail"]
    selected = [1]
    body, pinned = render_with_pins(
        sentences, selected,
        keep_headings=True, include_toc=False, pin=None,
        text="\n".join(sentences),
        headings=["Section A", "Appendix"],
    )
    assert "Appendix" in pinned
    assert "Appendix" in body


def test_legacy_rejects_headings_only():
    with pytest.raises(ValueError, match="legacy"):
        summarize("a b c d e f g.", max_length=300, mode="legacy", headings=["X"])


def test_override_keep_headings_title_unmatched_and_interleave():
    sentences = [
        "Syllabus",
        "The Court held X.",
        "Opinion of the Court",
        "The reasoning is Y.",
        "Costs were Z.",
    ]
    selected = [1, 3, 4]
    body, pinned = render_with_pins(
        sentences, selected,
        keep_headings=True, include_toc=False, pin=None,
        text="\n".join(sentences),
        headings=["Syllabus", "Opinion of the Court", "Dissent"],
    )
    assert body == (
        "Syllabus\n"
        "Dissent\n"
        "The Court held X.\n"
        "Opinion of the Court\n"
        "The reasoning is Y. Costs were Z."
    )
    assert pinned == ("Syllabus", "Dissent", "Opinion of the Court")


def test_override_toc_block():
    sentences = ["Body one here is long enough.", "Body two also."]
    body, pinned = render_with_pins(
        sentences, [0, 1],
        keep_headings=False, include_toc=True, pin=None,
        text="x", headings=["Syllabus", "Opinion", "Dissent"],
    )
    assert body == "Syllabus\nOpinion\nDissent\n\nBody one here is long enough. Body two also."
    assert pinned == ()


def test_override_none_falls_back_to_auto():
    sentences = ["# Title", "Body sentence one here.", "## Sub", "Body two here now."]
    a = render_with_pins(sentences, [1, 3], keep_headings=True, include_toc=False, pin=None, text="\n".join(sentences))
    b = render_with_pins(sentences, [1, 3], keep_headings=True, include_toc=False, pin=None, text="\n".join(sentences), headings=None)
    assert a == b


_DOC = (
    "Syllabus\n\n"
    "The Court held that the statute is constitutional under precedent.\n\n"
    "Opinion of the Court\n\n"
    "The reasoning rests on the commerce clause and prior rulings here.\n"
)


def test_summarize_headings_override_keep_headings():
    r = summarize(_DOC, max_length=300, keep_headings=True,
                  headings=["Syllabus", "Opinion of the Court", "Dissent"])
    assert r.summary.startswith("Syllabus")
    assert "Dissent" in r.pinned_headings
    assert "Opinion of the Court" in r.pinned_headings


def test_summarize_headings_override_toc():
    r = summarize(_DOC, max_length=300, include_toc=True,
                  headings=["Syllabus", "Opinion", "Dissent"])
    assert r.summary.startswith("Syllabus\nOpinion\nDissent\n\n")


def test_headings_without_flags_is_noop():
    base = summarize(_DOC, max_length=300).summary
    assert summarize(_DOC, max_length=300, headings=["Syllabus"]).summary == base


def test_headings_default_none_byte_identical():
    assert summarize(_DOC, max_length=300, keep_headings=True).summary == \
           summarize(_DOC, max_length=300, keep_headings=True, headings=None).summary


def test_legacy_rejects_headings():
    with pytest.raises(ValueError, match="legacy"):
        summarize(_DOC, max_length=300, mode="legacy", headings=["X"], include_toc=True)
