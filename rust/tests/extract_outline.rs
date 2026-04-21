use skimr::extract::outline::outline;

#[test]
fn outline_captures_markdown_sections() {
    let text = concat!(
        "# Introduction\n",
        "The team discussed the new pipeline. Sarah presented the charter.\n\n",
        "## Goals\n",
        "Decouple the ingest path. Shard writers for scale. Add backpressure.\n\n",
        "## Risks\n",
        "Data loss during cutover is the highest severity. ",
        "Unexpected consumer behavior is second."
    );
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(names.contains(&"Introduction"));
    assert!(names.contains(&"Goals"));
    assert!(names.contains(&"Risks"));
}

#[test]
fn outline_representative_is_non_heading_sentence() {
    let text = "## Results\nRevenue grew by 23 percent. Costs declined. Margins expanded.";
    let out = outline(text);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].name, "Results");
    assert!(out[0].representative_sentence != "## Results");
    let rs = &out[0].representative_sentence;
    assert!(
        rs.contains("Revenue") || rs.contains("Costs") || rs.contains("Margins"),
        "got: {rs:?}"
    );
}

#[test]
fn outline_depth_reflects_markdown_level() {
    let text = concat!(
        "# Top\nBody sentence one is here.\n\n",
        "## Mid\nMid body sentence one is here.\n\n",
        "### Deep\nDeep body sentence one is here."
    );
    let out = outline(text);
    let d: std::collections::HashMap<_, _> =
        out.iter().map(|s| (s.name.clone(), s.depth)).collect();
    assert_eq!(d.get("Top"), Some(&1));
    assert_eq!(d.get("Mid"), Some(&2));
    assert_eq!(d.get("Deep"), Some(&3));
}

#[test]
fn outline_returns_empty_for_no_headings() {
    let text = "Just some sentences. No headings here. Plain prose only.";
    let out = outline(text);
    assert!(out.is_empty());
}

#[test]
fn outline_tie_break_prefers_earlier_index_like_python() {
    // Regression for Python<->Rust tie-break parity. Construct a section whose
    // two body sentences produce identical composite scores, then assert that
    // Rust picks the earlier index — mirroring Python's `max(..., key=...)`
    // first-on-tie semantics.
    //
    // Structure (n=4 sentences after split): heading(0), body(1), body(2), heading(3).
    // - position_score with n=4 yields pos[1] == pos[2] (symmetric around the middle).
    // - Both body sentences share the same lowercased token set {alpha, beta,
    //   gamma, here}, so their tfidf contributions are identical.
    // - Both have the same word count, so length scores tie.
    // => composite score for idx 1 == composite score for idx 2.
    //
    // Pre-fix Rust (`max_by` returns last-max) picked "beta alpha gamma here."
    // Python picks "alpha beta gamma here." (the earlier index). This test
    // locks in parity with Python.
    let text = "# H\n\nalpha beta gamma here.\n\nbeta alpha gamma here.\n\n# End\n";
    let out = outline(text);
    let h = out
        .iter()
        .find(|s| s.name == "H")
        .expect("section H present");
    assert_eq!(h.representative_sentence, "alpha beta gamma here.");
}
