//! Tests for `skimr::brief` — at-a-glance document brief composition primitive.

use skimr::{brief, brief_with_options, BriefFormat, BriefOptions, BriefOutput};

const MULTI_SECTION: &str =
    "# Introduction\n\nThis report covers Q1 performance.\n\n\
     # Results\n\nRevenue grew 40 percent. Costs fell 10 percent. \
     Team size reached 50 users.\n\n\
     # Conclusion\n\nStrong quarter overall.\n";

#[test]
fn brief_default_returns_string() {
    let out = brief(MULTI_SECTION);
    assert!(out.contains("Overview:"));
    assert!(out.contains("Key facts:"));
    assert!(out.contains("Also in this doc:"));
    assert!(out.contains("Introduction"));
    assert!(out.contains("Results"));
    assert!(out.contains("Conclusion"));
}

#[test]
fn brief_dict_format_shape() {
    let opts = BriefOptions {
        format: BriefFormat::Dict,
        ..Default::default()
    };
    match brief_with_options(MULTI_SECTION, opts) {
        BriefOutput::Dict(d) => {
            assert!(!d.overview.is_empty());
            // toc should contain section names.
            assert!(d.toc.iter().any(|s| s == "Introduction"));
            assert!(d.toc.iter().any(|s| s == "Results"));
            // include_phrases=false by default → phrases should be None.
            assert!(d.phrases.is_none());
        }
        BriefOutput::Text(_) => panic!("expected Dict output for Dict format"),
    }
}

#[test]
fn brief_markdown_format_has_headers_and_bullets() {
    let text = "# Intro\n\nA document.\n\n# Details\n\nWe processed 1,000 events.\n";
    let opts = BriefOptions {
        format: BriefFormat::Markdown,
        ..Default::default()
    };
    match brief_with_options(text, opts) {
        BriefOutput::Text(s) => {
            assert!(s.contains("## Overview"));
            assert!(s.contains("## Also in this doc"));
            assert!(s.contains("- Intro"));
            assert!(s.contains("- Details"));
        }
        BriefOutput::Dict(_) => panic!("expected Text output for Markdown format"),
    }
}

#[test]
fn brief_include_phrases_flips_behavior() {
    let text =
        "# Section\n\nCustomer support team handles deployment pipeline work. \
         The customer support team reviews requests. \
         Our deployment pipeline processes events. \
         Customer support team also handles incidents.\n";
    let opts = BriefOptions {
        include_phrases: true,
        format: BriefFormat::Dict,
        ..Default::default()
    };
    match brief_with_options(text, opts) {
        BriefOutput::Dict(d) => {
            let phrases = d.phrases.expect("phrases requested, should be Some");
            assert!(!phrases.is_empty());
        }
        BriefOutput::Text(_) => panic!("expected Dict output"),
    }

    // Default path: phrases field is None.
    let default_opts = BriefOptions {
        format: BriefFormat::Dict,
        ..Default::default()
    };
    match brief_with_options(text, default_opts) {
        BriefOutput::Dict(d) => assert!(d.phrases.is_none()),
        BriefOutput::Text(_) => panic!("expected Dict output"),
    }
}

#[test]
fn brief_overview_max_clamped() {
    // Below floor: clamps to 0.05 internally — no panic.
    let opts_low = BriefOptions {
        overview_max: 0.01,
        ..Default::default()
    };
    let _ = brief_with_options("Short doc. Two sentences.", opts_low);

    // Above ceiling: clamps to 0.50 internally — no panic.
    let opts_high = BriefOptions {
        overview_max: 0.99,
        ..Default::default()
    };
    let _ = brief_with_options("Short doc. Two sentences.", opts_high);
}

#[test]
fn brief_handles_empty_text() {
    let out = brief("");
    assert!(out.contains("Overview:"));
    // With empty input there are no facts and no sections.
    assert!(!out.contains("Key facts:"));
    assert!(!out.contains("Also in this doc:"));
}

#[test]
fn brief_string_trails_single_newline() {
    let out = brief(MULTI_SECTION);
    assert!(out.ends_with('\n'));
    // Exactly one trailing newline — Python uses `.rstrip() + "\n"`.
    assert!(!out.ends_with("\n\n"));
}
