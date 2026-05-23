use lede::Mode;
use lede::pins::{
    document_title_index, nearest_heading_map, render_toc_from_list, render_with_pins,
};
use lede::tfidf::{PinOpts, SummarizeOpts, summarize_with_pins};

fn sentences() -> Vec<String> {
    [
        "# Quarterly Report",
        "Revenue rose sharply this quarter overall.",
        "## Revenue",
        "Revenue grew twelve percent year over year.",
        "Costs were flat across the period.",
        "## Risks",
        "Supply chain risk remains elevated this year.",
    ]
    .iter()
    .map(std::string::ToString::to_string)
    .collect()
}

#[test]
fn nearest_heading_map_matches_python() {
    let s = sentences();
    assert_eq!(
        nearest_heading_map(&s),
        vec![None, Some(0), None, Some(2), Some(2), None, Some(5)]
    );
}

#[test]
fn document_title_index_depth1_at_start() {
    let s = sentences();
    assert_eq!(document_title_index(&s), Some(0));
}

#[test]
fn summarize_with_pins_pins_title_default_mode() {
    let doc = "# Quarterly Report\n\nRevenue rose sharply this quarter across every region we serve.\n\n## Revenue\n\nRevenue grew twelve percent year over year to record levels.\nOperating costs stayed essentially flat across the whole period.\n\n## Risks\n\nSupply chain risk remains elevated heading into the next year.\n";
    let pin_opts = PinOpts {
        keep_headings: true,
        include_toc: false,
        pin: Vec::new(),
        ..Default::default()
    };
    let r = summarize_with_pins(
        doc,
        200,
        Mode::Default,
        &SummarizeOpts::default(),
        &pin_opts,
    );
    assert!(r.summary.starts_with("# Quarterly Report"));
    assert!(
        r.pinned_headings
            .contains(&"# Quarterly Report".to_string())
    );
}

#[test]
fn render_keep_headings_interleaves() {
    let s = sentences();
    let (body, pinned) = render_with_pins(&s, &[1, 3, 6], true, false, None, &s.join("\n"), None);
    assert_eq!(pinned, vec!["# Quarterly Report", "## Revenue", "## Risks"]);
    assert_eq!(
        body,
        "# Quarterly Report\nRevenue rose sharply this quarter overall.\n## Revenue\nRevenue grew twelve percent year over year.\n## Risks\nSupply chain risk remains elevated this year."
    );
}

#[test]
fn render_toc_from_list_dedupes_preserves_order() {
    let h: Vec<String> = ["A", "B", "A", "C"]
        .iter()
        .map(std::string::ToString::to_string)
        .collect();
    assert_eq!(render_toc_from_list(&h), "A\nB\nC");
}

#[test]
fn override_keep_headings_title_unmatched_and_interleave() {
    let sentences: Vec<String> = [
        "Syllabus",
        "The Court held X.",
        "Opinion of the Court",
        "The reasoning is Y.",
        "Costs were Z.",
    ]
    .iter()
    .map(std::string::ToString::to_string)
    .collect();
    let headings: Vec<String> = ["Syllabus", "Opinion of the Court", "Dissent"]
        .iter()
        .map(std::string::ToString::to_string)
        .collect();
    let (body, pinned) = render_with_pins(
        &sentences,
        &[1, 3, 4],
        true,
        false,
        None,
        &sentences.join("\n"),
        Some(&headings),
    );
    assert_eq!(
        body,
        "Syllabus\nDissent\nThe Court held X.\nOpinion of the Court\nThe reasoning is Y. Costs were Z."
    );
    assert_eq!(pinned, vec!["Syllabus", "Dissent", "Opinion of the Court"]);
}

#[test]
fn summarize_with_pins_headings_override() {
    use lede::Mode;
    use lede::tfidf::{PinOpts, SummarizeOpts, summarize_with_pins};

    let doc = "Syllabus\n\nThe Court held that the statute is constitutional under precedent.\n\nOpinion of the Court\n\nThe reasoning rests on the commerce clause and prior rulings here.\n";
    let pin_opts = PinOpts {
        keep_headings: true,
        include_toc: false,
        pin: Vec::new(),
        headings: ["Syllabus", "Opinion of the Court", "Dissent"]
            .iter()
            .map(std::string::ToString::to_string)
            .collect(),
    };
    let r = summarize_with_pins(
        doc,
        300,
        Mode::Default,
        &SummarizeOpts::default(),
        &pin_opts,
    );
    assert!(r.summary.starts_with("Syllabus"));
    assert!(r.pinned_headings.contains(&"Dissent".to_string()));
    assert!(
        r.pinned_headings
            .contains(&"Opinion of the Court".to_string())
    );
}

#[test]
fn override_matched_but_unselected_heading_still_survives() {
    // "Appendix" matches body index 2 but its section (index 3) is not
    // selected, so interleave never reaches it. It must still appear
    // (spec §4.3 step 6: every supplied heading is guaranteed present).
    let sentences: Vec<String> = ["Section A", "body one here", "Appendix", "appendix detail"]
        .iter()
        .map(std::string::ToString::to_string)
        .collect();
    let headings: Vec<String> = ["Section A", "Appendix"]
        .iter()
        .map(std::string::ToString::to_string)
        .collect();
    let (body, pinned) = render_with_pins(
        &sentences,
        &[1],
        true,
        false,
        None,
        &sentences.join("\n"),
        Some(&headings),
    );
    assert!(pinned.contains(&"Appendix".to_string()));
    assert!(body.contains("Appendix"));
}
