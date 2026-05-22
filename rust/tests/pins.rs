use lede::Mode;
use lede::pins::{document_title_index, nearest_heading_map, render_with_pins};
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
    let (body, pinned) = render_with_pins(&s, &[1, 3, 6], true, false, None, &s.join("\n"));
    assert_eq!(pinned, vec!["# Quarterly Report", "## Revenue", "## Risks"]);
    assert_eq!(
        body,
        "# Quarterly Report\nRevenue rose sharply this quarter overall.\n## Revenue\nRevenue grew twelve percent year over year.\n## Risks\nSupply chain risk remains elevated this year."
    );
}
