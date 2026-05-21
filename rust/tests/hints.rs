use lede::Mode;
use lede::brief::{BriefOptions, brief_with_options};
use lede::extract::correlate::correlate_facts_with_hints;
use lede::extract::key_facts::{KeyFactsOptions, key_facts_with_options};
use lede::extract::phrases::phrases_with_hints;
use lede::extract::stats::StatsOptions;
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

// ---- parity spot-check against Python reference strings ----
// These are the exact bytes Python produces. If T13's fixture walker is green,
// these will trivially pass — but catching them now validates the logic before
// fixtures exist.

const PY_NO_HINTS: &str = "The town council met on Tuesday. John Smith presented his case to the assembly. Smith argued for lower property taxes. Local farmers expressed concern about water rights. The next meeting is scheduled for the third of next month. John Smith lives in Cook County and runs a small business.";
const PY_SOFT: &str = "Cook County is the second-most populous county in Illinois. The next meeting is scheduled for the third of next month. John Smith lives in Cook County and runs a small business.";
const PY_HARD: &str = "John Smith presented his case to the assembly. Smith argued for lower property taxes. John Smith lives in Cook County and runs a small business.";
const PY_FOCUS_ZERO: &str = "The town council met on Tuesday. John Smith presented his case to the assembly. Smith argued for lower property taxes. Local farmers expressed concern about water rights. The next meeting is scheduled for the third of next month. John Smith lives in Cook County and runs a small business.";

#[test]
fn parity_no_hints_byte_identical() {
    let opts = SummarizeOpts::default();
    let result = summarize_with_hints(SAMPLE, 300, Mode::Default, &opts).summary;
    assert_eq!(
        result, PY_NO_HINTS,
        "no-hints path must match Python byte-for-byte"
    );
}

#[test]
fn parity_soft_hints_byte_identical() {
    let opts = SummarizeOpts {
        hints: vec![("john smith".to_string(), 1.0), ("county".to_string(), 1.0)],
        hint_focus: 0.7,
        hint_mode: HintMode::Soft,
    };
    let result = summarize_with_hints(SAMPLE, 200, Mode::Default, &opts).summary;
    assert_eq!(
        result, PY_SOFT,
        "soft hints must match Python byte-for-byte"
    );
}

#[test]
fn parity_hard_hints_byte_identical() {
    let opts = SummarizeOpts {
        hints: vec![("smith".to_string(), 1.0)],
        hint_focus: 1.0,
        hint_mode: HintMode::Hard,
    };
    let result = summarize_with_hints(SAMPLE, 200, Mode::Default, &opts).summary;
    assert_eq!(
        result, PY_HARD,
        "hard hints must match Python byte-for-byte"
    );
}

#[test]
fn parity_focus_zero_byte_identical() {
    let opts = SummarizeOpts {
        hints: vec![("county".to_string(), 1.0)],
        hint_focus: 0.0,
        hint_mode: HintMode::Soft,
    };
    let result = summarize_with_hints(SAMPLE, 300, Mode::Default, &opts).summary;
    assert_eq!(
        result, PY_FOCUS_ZERO,
        "focus=0.0 must match Python byte-for-byte"
    );
}

// ---- T11: key_facts, phrases, correlate_facts, brief hint kwargs ----

#[test]
fn key_facts_hard_filter_all_match() {
    let text = "The company earned $5 million in Q3 2023. \
Smith filed the annual report on March 15, 2024. \
Total employees grew by 12 percent to 450 staff. \
Revenue fell 8 percent year-over-year to $4.2 billion.";
    let opts = KeyFactsOptions {
        max_facts: 10,
        hints: vec![("smith".to_string(), 1.0)],
        hint_focus: 1.0,
        hint_mode: HintMode::Hard,
        ..Default::default()
    };
    let facts = key_facts_with_options(text, opts);
    for f in &facts {
        assert!(f.to_lowercase().contains("smith"), "LEAK: {f:?}");
    }
}

#[test]
fn key_facts_no_hints_byte_identical() {
    let text = SAMPLE;
    let a = lede::extract::key_facts::key_facts(text, 5);
    let opts = KeyFactsOptions {
        max_facts: 5,
        ..Default::default()
    };
    let b = key_facts_with_options(text, opts);
    assert_eq!(a, b);
}

#[test]
fn phrases_hard_filter_only_match() {
    let text = "Cook County board met. Cook County reviewed. Acme Corp filed reports. Acme Corp earned revenue.";
    let out = phrases_with_hints(text, None, &[("county".to_string(), 1.0)], HintMode::Hard);
    for p in &out {
        assert!(p.to_lowercase().contains("county"), "LEAK: {p:?}");
    }
    assert!(!out.is_empty(), "expected at least one county phrase");
}

#[test]
fn phrases_soft_preserves_all_candidates() {
    let text = "Cook County board met. Cook County reviewed. Acme Corp filed reports. Acme Corp earned revenue.";
    let no_hints = lede::extract::phrases::phrases(text, None);
    let soft = phrases_with_hints(text, None, &[("county".to_string(), 1.0)], HintMode::Soft);
    let no_set: std::collections::HashSet<_> = no_hints.iter().cloned().collect();
    let soft_set: std::collections::HashSet<_> = soft.iter().cloned().collect();
    assert_eq!(no_set, soft_set, "soft mode dropped candidates");
}

#[test]
fn correlate_hard_filter_or_semantics() {
    let text = "Cook County reported 5 percent growth. \
Cook County board approved 5 percent budget increase. \
Acme Corp earned 2 billion in Q3. \
Acme Corp announced 2 billion revenue.";
    let out = correlate_facts_with_hints(
        text,
        StatsOptions::default(),
        &[("county".to_string(), 1.0)],
        HintMode::Hard,
    );
    for pf in &out {
        let target = format!("{} {}", pf.entity, pf.number).to_lowercase();
        assert!(target.contains("county"), "LEAK: {pf:?}");
    }
}

#[test]
fn brief_forwards_hints_to_summarize() {
    let opts = BriefOptions {
        overview_max: 0.5,
        max_facts: 5,
        hints: vec![("john smith".to_string(), 1.0), ("county".to_string(), 1.0)],
        hint_focus: 1.0,
        hint_mode: HintMode::Soft,
        ..Default::default()
    };
    let output = brief_with_options(SAMPLE, opts);
    match output {
        lede::brief::BriefOutput::Text(s) => {
            let low = s.to_lowercase();
            assert!(
                low.contains("smith") || low.contains("county"),
                "no hint in {s}"
            );
        }
        lede::brief::BriefOutput::Dict(_) => panic!("expected Text output"),
    }
}
