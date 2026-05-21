use lede::Mode;
use lede::hints::HintMode;
use lede::tfidf::{SummarizeOpts, summarize_with_hints};

const SAMPLE: &str = "The town council met on Tuesday. \
John Smith presented his case to the assembly. \
Smith argued for lower property taxes. \
The council voted to defer the decision. \
Cook County is the second-most populous county in Illinois. \
Local farmers expressed concern about water rights. \
The next meeting is scheduled for the third of next month. \
John Smith lives in Cook County and runs a small business.";

#[test]
fn backward_compat_no_hints() {
    let opts = SummarizeOpts::default();
    let a = lede::summarize(SAMPLE, 300, Mode::Default);
    let b = summarize_with_hints(SAMPLE, 300, Mode::Default, &opts);
    assert_eq!(a.summary, b.summary);
}

#[test]
fn soft_hints_surface_matching_sentences() {
    let opts = SummarizeOpts {
        hints: vec![("john smith".to_string(), 1.0), ("county".to_string(), 1.0)],
        hint_focus: 0.7,
        hint_mode: HintMode::Soft,
    };
    let result = summarize_with_hints(SAMPLE, 200, Mode::Default, &opts).summary;
    assert!(
        result.contains("John Smith") || result.contains("Cook County"),
        "expected hint match in {result:?}"
    );
}

#[test]
fn hard_full_focus_only_matches() {
    let opts = SummarizeOpts {
        hints: vec![("smith".to_string(), 1.0)],
        hint_focus: 1.0,
        hint_mode: HintMode::Hard,
    };
    let result = summarize_with_hints(SAMPLE, 200, Mode::Default, &opts).summary;
    for sent in result.split(". ") {
        let trimmed = sent.trim_matches(|c: char| c == '.' || c.is_whitespace());
        if !trimmed.is_empty() {
            assert!(
                trimmed.to_lowercase().contains("smith"),
                "non-matching sentence leaked: {trimmed:?}"
            );
        }
    }
}

#[test]
fn hard_full_focus_rollover_stays_restricted() {
    // Stat-bearing context with only some sentences containing the hint.
    // If the hard-mode rollover used plain_scores it would leak non-Smith sentences.
    let text = "The company earned $5 million in Q3 2023. \
Smith filed the annual report on March 15, 2024. \
Total employees grew by 12 percent to 450 staff. \
Revenue fell 8 percent year-over-year to $4.2 billion.";
    let opts = SummarizeOpts {
        hints: vec![("smith".to_string(), 1.0)],
        hint_focus: 1.0,
        hint_mode: HintMode::Hard,
    };
    let result = summarize_with_hints(text, 200, Mode::Default, &opts).summary;
    for sent in result.split(". ") {
        let trimmed = sent.trim_matches(|c: char| c == '.' || c.is_whitespace());
        if !trimmed.is_empty() {
            assert!(
                trimmed.to_lowercase().contains("smith"),
                "leak: {trimmed:?}"
            );
        }
    }
}

#[test]
fn focus_zero_equals_no_hints() {
    let a = lede::summarize(SAMPLE, 300, Mode::Default);
    let opts = SummarizeOpts {
        hints: vec![("county".to_string(), 1.0)],
        hint_focus: 0.0,
        hint_mode: HintMode::Soft,
    };
    let b = summarize_with_hints(SAMPLE, 300, Mode::Default, &opts);
    assert_eq!(a.summary, b.summary);
}

#[test]
fn empty_hints_equals_no_hints() {
    let a = lede::summarize(SAMPLE, 300, Mode::Default);
    let opts = SummarizeOpts::default();
    let b = summarize_with_hints(SAMPLE, 300, Mode::Default, &opts);
    assert_eq!(a.summary, b.summary);
}

#[test]
#[should_panic(expected = "hints not supported in legacy mode")]
fn legacy_mode_with_hints_panics() {
    let opts = SummarizeOpts {
        hints: vec![("smith".to_string(), 1.0)],
        hint_focus: 0.7,
        hint_mode: HintMode::Soft,
    };
    let _ = summarize_with_hints(SAMPLE, 200, Mode::Legacy, &opts);
}

#[test]
fn coverage_mode_accepts_hints() {
    let opts = SummarizeOpts {
        hints: vec![("county".to_string(), 1.0)],
        hint_focus: 0.7,
        hint_mode: HintMode::Soft,
    };
    let result = summarize_with_hints(SAMPLE, 200, Mode::Coverage, &opts).summary;
    assert!(!result.is_empty(), "coverage mode should produce a summary");
}
