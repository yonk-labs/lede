use skimr::extract::outline::{outline, toc};

#[test]
fn toc_returns_section_names_in_order() {
    let text = concat!(
        "# Introduction\n\nSome intro text.\n\n",
        "# Methods\n\nSome methods.\n\n",
        "# Results\n\nSome results.\n",
    );
    let out = toc(text);
    assert_eq!(
        out,
        vec![
            "Introduction".to_string(),
            "Methods".to_string(),
            "Results".to_string()
        ]
    );
}

#[test]
fn toc_matches_outline_names() {
    let text = concat!(
        "## Section A\n\nBody sentence one.\n\n",
        "## Section B\n\nBody sentence two.\n",
    );
    let expected: Vec<String> = outline(text).into_iter().map(|s| s.name).collect();
    assert_eq!(toc(text), expected);
}

#[test]
fn toc_empty_for_text_without_headings() {
    let text = "This is a paragraph without any heading structure. Just prose here.";
    assert!(toc(text).is_empty());
}
