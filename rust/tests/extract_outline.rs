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

#[test]
fn outline_extracts_bare_title_case_headings() {
    // T13b Class A: bare title-case single-line headings.
    let text = concat!(
        "Title: Test Paper\n\nAbstract\n\nWe investigate.\n\n",
        "Introduction\n\nDeterministic output matters.\n\n",
        "Conclusion\n\nFix is trivial.\n",
    );
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(names.contains(&"Abstract"), "names = {names:?}");
    assert!(names.contains(&"Introduction"), "names = {names:?}");
    assert!(names.contains(&"Conclusion"), "names = {names:?}");
}

#[test]
fn outline_extracts_numbered_sections() {
    // T13b Class B: `\d+. Section Name` with prefix stripped from name.
    let text = concat!(
        "Privacy Policy\n\n",
        "1. Information We Collect\n\nWe collect data.\n\n",
        "2. How We Use Information\n\nWe process it.\n",
    );
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(
        names.contains(&"Information We Collect"),
        "names = {names:?}"
    );
    assert!(
        names.contains(&"How We Use Information"),
        "names = {names:?}"
    );
}

#[test]
fn outline_extracts_long_allcaps_title() {
    // T13b Class C: ALLCAPS headings up to 80 chars.
    let text = concat!(
        "SUPREME COURT OF THE UNITED STATES\n\n",
        "Opinion follows here with enough body to form a section.\n",
    );
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(
        names.contains(&"SUPREME COURT OF THE UNITED STATES"),
        "names = {names:?}"
    );
}

#[test]
fn outline_still_excludes_short_body_sentences() {
    // T13b regression: short body sentences like "Costs declined." must NOT match.
    // Terminal period excludes them from bare_title_re.
    let text = "# Finance\n\nCosts declined. Revenue grew by 20 percent.\n";
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(!names.contains(&"Costs declined"), "names = {names:?}");
    assert!(names.contains(&"Finance"), "names = {names:?}");
}

#[test]
fn outline_extracts_em_dash_title_line() {
    // T13d: "Privacy Policy — Effective Date: ..." → heading "Privacy Policy".
    // Labeling protocol authorizes stripping em-dash metadata on title lines.
    let text = concat!(
        "Privacy Policy \u{2014} Effective Date: 2026-01-01\n\n",
        "This policy describes how we handle your data.\n\n",
        "Further details follow.\n",
    );
    let out = outline(text);
    let names: Vec<&str> = out.iter().map(|s| s.name.as_str()).collect();
    assert!(names.contains(&"Privacy Policy"), "names = {names:?}");
    // Must NOT include the em-dash suffix in the name:
    assert!(
        !names.iter().any(|n| n.contains('\u{2014}') || n.contains('\u{2013}')),
        "names = {names:?}"
    );
}
