from lede._pins import render_toc_from_list, render_with_pins


def test_render_toc_from_list_dedupes_preserves_order():
    assert render_toc_from_list(["A", "B", "A", "C"]) == "A\nB\nC"


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
