from skimr.extract import toc, outline


def test_toc_returns_section_names_in_order():
    text = (
        "# Introduction\n\nSome intro text.\n\n"
        "# Methods\n\nSome methods.\n\n"
        "# Results\n\nSome results.\n"
    )
    assert toc(text) == ("Introduction", "Methods", "Results")


def test_toc_matches_outline_names():
    text = (
        "## Section A\n\nBody sentence one.\n\n"
        "## Section B\n\nBody sentence two.\n"
    )
    assert toc(text) == tuple(s.name for s in outline(text))


def test_toc_empty_for_text_without_headings():
    text = "This is a paragraph without any heading structure. Just prose here."
    assert toc(text) == ()
